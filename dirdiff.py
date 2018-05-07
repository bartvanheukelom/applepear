import os
import hashlib

from typing import List, Callable, Set, Dict, Any, Tuple, NewType

AbstractPath = NewType('AbstractPath', str)
Difference = NewType('Difference', str)
FilePath = NewType('FilePath', str)


class TreeNode:
    def __init__(self):
        self.path: AbstractPath = None
        self.differences: Set[Difference] = set()
        self.existsIn: Set[int] = set()

        # TODO actions probably belong in dirdiffgui
        self.actions: List[Tuple[str, List[str]]] = []


class TreeDir(TreeNode):
    def __init__(self):
        super().__init__()
        self.subdirs: Dict[str, TreeDir] = dict()
        self.files: Dict[str, TreeFile] = dict()


class TreeFile(TreeNode):
    def __init__(self):
        super().__init__()


def path_per_cd(name: AbstractPath, dirs: List[FilePath]) -> List[FilePath]:
    return [FilePath(d + '/' + name) for d in dirs]


def hashfiles(files: List[FilePath]) -> str:
    h = hashlib.sha256()
    for file in files:
        if os.path.exists(file):
            with open(file, 'rb', buffering=0) as f:
                for b in iter(lambda: f.read(128 * 1024), b''):
                    h.update(b)
    return h.hexdigest()


def getcontents(fn: FilePath) -> bytes:
    with open(fn, 'rb') as of:
        return of.read()


# the typo is intended
class Compearison:

    def __init__(self, dirs_to_compare: List[FilePath], dir_names: List[str],
                 should_include: Callable[[AbstractPath], bool], add_ignore: Callable[[AbstractPath], None]):

        self.dirs_to_compare = dirs_to_compare
        self.add_ignore = add_ignore
        self.dir_names = dir_names

        self.root = TreeDir()

        # index all files that exist in either directory
        for i in range(0, len(dirs_to_compare)):
            base = dirs_to_compare[i]

            self.root.existsIn.add(i)

            for f in os.walk(base, True):
                path, subdirs, files = f
                rel_path = AbstractPath(path[len(base) + 1:])

                if not should_include(rel_path):
                    subdirs.clear()
                    continue

                node = self.root
                if rel_path != '':
                    for p in rel_path.split('/'):
                        node = node.subdirs.get(p) or node.subdirs.setdefault(p, TreeDir())
                        node.existsIn.add(i)

                for sf in files:
                    if rel_path == '':
                        fp = sf
                    else:
                        fp = rel_path + '/' + sf
                    if not should_include(AbstractPath(fp)):
                        continue

                    file = node.files.get(sf) or node.files.setdefault(sf, TreeFile())
                    file.existsIn.add(i)

        self.compare(AbstractPath('.'), self.root)

    def compare(self, name: AbstractPath, node: TreeNode):
        node.path = name

        for i in range(0, len(self.dirs_to_compare)):
            if i not in node.existsIn:
                side_has = self.dir_names[(i + 1) % 2]
                side_missing = self.dir_names[i]
                node.differences.add(Difference('only-in-' + side_has))

                pa_left, pa_right = path_per_cd(name, self.dirs_to_compare)
                if i == 0:
                    # missing left
                    pa_has = pa_right
                    node.actions += [('Left=delete-' + side_has,
                                      ['rm', '-rv', pa_right])]
                    node.actions += [('Right=copy-' + side_has + '-to-' + side_missing,
                                      ['cp', '-rv', pa_right, pa_left])]
                elif i == 1:
                    # missing right
                    pa_has = pa_left
                    node.actions += [('Left=copy-' + side_has + '-to-' + side_missing,
                                      ['cp', '-rv', pa_left, pa_right])]
                    node.actions += [('Right=delete-' + side_has,
                                      ['rm', '-rv', pa_left])]

                node.actions += [('View', ['cat', pa_has])]

        if isinstance(node, TreeDir):
            for mp in [node.subdirs, node.files]:
                for sn, info in mp.items():
                    self.compare(AbstractPath(name + '/' + sn), info)
                    if info.differences:
                        node.differences.add(Difference('sub'))
        else:
            if not node.differences:

                def compareattrs(getter: Callable[[str], Any]):
                    val = None
                    for pp in path_per_cd(name, self.dirs_to_compare):
                        cv = getter(pp)
                        if val is None:
                            val = cv
                        elif cv != val:
                            return True

                if compareattrs(lambda fn: os.stat(fn).st_size):
                    node.differences.add(Difference('size'))
                elif compareattrs(getcontents):
                    node.differences.add(Difference('content'))

                if node.differences:
                    p = path_per_cd(name, self.dirs_to_compare)
                    node.actions += [('Diff', ['diff'] + p)]
                    node.actions += [('Meld', ['meld'] + p)]
                    node.actions += [('Leftboth', ['cp', '-rv'] + p)]
                    node.actions += [('Rightboth', ['cp', '-rv'] + list(reversed(p)))]

        if node.differences:
            node.actions += [('Ignore', lambda: self.add_ignore(name))]
