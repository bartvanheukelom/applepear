import os
import hashlib

from typing import List, Callable, Set, Dict, Any, Tuple


class TreeNode:
    def __init__(self):
        self.path: str = None
        self.differences: Set[str] = set()
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


def path_per_cd(name: str, dirs: List[str]) -> List[str]:
    return [cd + '/' + name for cd in dirs]


def hashfiles(files: List[str]) -> str:
    h = hashlib.sha256()
    for file in files:
        with open(file, 'rb', buffering=0) as f:
            for b in iter(lambda: f.read(128 * 1024), b''):
                h.update(b)
    return h.hexdigest()


def getcontents(fn: str) -> bytes:
    with open(fn, 'rb') as of:
        return of.read()


# the typo is intended
class Compearison:

    def __init__(self, dirs_to_compare: List[str], dir_names: List[str],
                 should_include: Callable[[str], bool], add_ignore: Callable[[str], None]):

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
                rel_path = path[len(base) + 1:]

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
                    if not should_include(fp):
                        continue

                    file = node.files.get(sf) or node.files.setdefault(sf, TreeFile())
                    file.existsIn.add(i)

        self.compare('.', self.root)

    def compare(self, name: str, node: TreeNode):
        node.path = name

        for i in range(0, len(self.dirs_to_compare)):
            if i not in node.existsIn:
                node.differences.add('missing_' + self.dir_names[i])

                side_has = self.dir_names[(i + 1) % 2]
                side_missing = self.dir_names[i]

                p = path_per_cd(name, self.dirs_to_compare)
                if i == 0:
                    p = list(reversed(p))
                pa_has, pa_missing = p

                node.actions += [('Copy-' + side_has + '-to-' + side_missing, ['cp', '-rv', pa_has, pa_missing])]
                node.actions += [('Delete-' + side_has, ['rm', '-rv', pa_has])]
                node.actions += [('View', ['cat', pa_has])]

        if isinstance(node, TreeDir):
            for mp in [node.subdirs, node.files]:
                for sn, info in mp.items():
                    self.compare(name + '/' + sn, info)
                    if info.differences:
                        node.differences.add('sub')
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
                    node.differences.add('size')
                elif compareattrs(getcontents):
                    node.differences.add('content')

                if node.differences:
                    p = path_per_cd(name, self.dirs_to_compare)
                    node.actions += [('Diff', ['diff'] + p)]
                    node.actions += [('Meld', ['meld'] + p)]
                    node.actions += [('Leftboth', ['cp', '-rv'] + p)]
                    node.actions += [('Rightboth', ['cp', '-rv'] + list(reversed(p)))]

        if node.differences:
            node.actions += [('Ignore', lambda: self.add_ignore(name))]
