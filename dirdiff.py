import os
import hashlib

class TreeNode:
    def __init__(self):
        self.path = None
        # TODO actions probably belong in dirdiffgui
        self.actions = []
        self.differences = set()
        self.existsIn = set()
        self.isDir = isinstance(self, TreeDir)

class TreeDir(TreeNode):
    def __init__(self):
        super().__init__()
        self.subdirs = dict()
        self.files = dict()


class TreeFile(TreeNode):
    def __init__(self):
        super().__init__()

def pathPerCd(name, dirs):
    return [cd + '/' + name for cd in dirs]

def hashfiles(files):
    h = hashlib.sha256()
    for file in files:
        with open(file, 'rb', buffering=0) as f:
            for b in iter(lambda : f.read(128*1024), b''):
                h.update(b)
    return h.hexdigest()

def runComparison(dirs_to_compare, dir_names, should_include, add_ignore):

    root = TreeDir()

    for i in range(0, len(dirs_to_compare)):
        base = dirs_to_compare[i]

        root.existsIn.add(i)

        for f in os.walk(base, True):
            path, subdirs, files = f
            relPath = path[len(base)+1:]

            if not should_include(relPath):
                subdirs.clear()
                continue

            node = root
            if relPath != '':
                for p in relPath.split('/'):
                    node = node.subdirs.get(p) or node.subdirs.setdefault(p, TreeDir())
                    node.existsIn.add(i)

            for sf in files:
                if relPath == '': fp = sf
                else: fp = relPath + '/' + sf
                if not should_include(fp):
                    continue

                file = node.files.get(sf) or node.files.setdefault(sf, TreeFile())
                file.existsIn.add(i)

    def getcontents(fn):
        with open(fn, 'rb') as of:
            return of.read()

    def compare(name, node):

        node.path = name

        for i in range(0, len(dirs_to_compare)):
            if i not in node.existsIn:
                node.differences.add('missing_' + dir_names[i])

                sideHas = dir_names[(i+1)%2]
                sideMissing = dir_names[i]

                p = pathPerCd(name, dirs_to_compare)
                if i == 0: p = list(reversed(p))
                paHas, paMissing = p

                node.actions += [('Copy-' + sideHas + '-to-' + sideMissing, ['cp', '-rv', paHas, paMissing])]
                node.actions += [('Delete-' + sideHas, ['rm','-rv', paHas])]
                node.actions += [('View', ['cat', paHas])]

        if node.isDir:
            for mp in [node.subdirs, node.files]:
                for sn, info in mp.items():
                    compare(name + '/' + sn, info)
                    if info.differences:
                        node.differences.add('sub')
        else:
            if not node.differences:

                def compareattrs(getter):
                    val = None
                    for p in pathPerCd(name, dirs_to_compare):
                        cv = getter(p)
                        if val is None: val = cv
                        elif cv != val: return True

                if compareattrs(lambda fn: os.stat(fn).st_size):
                    node.differences.add('size')
                elif compareattrs(getcontents):
                    node.differences.add('content')

                if node.differences:
                    p = pathPerCd(name, dirs_to_compare)
                    node.actions += [('Diff', ['diff'] + p)]
                    node.actions += [('Meld', ['meld'] + p)]
                    node.actions += [('Leftboth', ['cp', '-rv'] + p)]
                    node.actions += [('Rightboth', ['cp', '-rv'] + list(reversed(p)))]

        if node.differences:
            node.actions += [('Ignore', lambda: add_ignore(name))]

    compare('.', root)

    return root

