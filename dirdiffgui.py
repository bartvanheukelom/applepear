# coding=utf-8

from typing import List, Optional, TypeVar, Callable, Tuple
import subprocess
import dirdiff
import curses
import iutil
import hexes

T = TypeVar('T')


class Line:
    def __init__(self, displayname: str, info: dirdiff.TreeNode):
        self.displayname = displayname
        self.info = info


def navigate_list(lyst: List[T], cur: T, direction: int):
    if cur is None:
        return None if len(lyst) == 0 else lyst[0]
    else:
        return lyst[(lyst.index(cur) + direction) % len(lyst)]


class ApplePearTUI:

    def __init__(self, basedir: dirdiff.FilePath, dirs_to_compare: List[Tuple[str, dirdiff.FilePath]],
                 should_include_: Callable[[dirdiff.AbstractPath], bool], path_shortcuts_,
                 add_ignore_: Callable[[dirdiff.AbstractPath], None]):

        self.basedir = basedir
        self.dirs_to_compare = dirs_to_compare
    
        # TODO replace
        self.compareDirNames = [n for n, p in dirs_to_compare]
        self.compareDirs = [basedir + '/' + p for n, p in dirs_to_compare]

        self.shouldInclude = should_include_
        self.path_shortcuts = path_shortcuts_
        self.add_ignore = add_ignore_

        # state
        self.selected_line: Optional[Line] = None
        self.lines: List[Line] = []
        self.temp_status_bar: str = None

    def run(self):

        self.compare()
        while True:
            # loop can return an intermezzo function that should be invoked outside of curses
            intermezzo = curses.wrapper(self.cursesloop)
            if not intermezzo: break
            intermezzo()

    def path_per_cd(self, rp: dirdiff.AbstractPath) -> List[dirdiff.FilePath]:
        return dirdiff.path_per_cd(rp, self.compareDirs)

    def flatten(self, prefix: str, name: str, info: dirdiff.TreeNode, depth=0):

        if not info.differences:
            return

        if depth == 0:
            fullname = '.'
        elif prefix == '.':
            fullname = name
        else:
            fullname = prefix + '/' + name

        # recursively apply shortcuts
        displayname = fullname
        while True:
            before = displayname
            for x, y in self.path_shortcuts:
                displayname = displayname.replace(x, y)
            if displayname == before: break

        # make more readable
        displayname = displayname.replace('/', ' / ')

        # add only real differences
        if info.differences != {'sub'}:
            self.lines.append(Line(displayname, info))

        # recurse
        if isinstance(info, dirdiff.TreeDir):
            for mp in [info.subdirs, info.files]:
                for sn in sorted(mp.keys()):
                    self.flatten(fullname, sn, mp[sn], depth + 1)

    def compare(self):

        # compare the dirs
        root = dirdiff.Compearison(self.compareDirs, self.compareDirNames, self.shouldInclude, self.add_ignore).root

        # preserve the selection index
        selindex = 0 if self.selected_line is None else self.lines.index(self.selected_line)

        # flatten the result to a list of lines
        self.lines = []
        self.flatten('', '', root)

        # restore selection from index
        self.selected_line = None if len(self.lines) == 0 else self.lines[min(len(self.lines) - 1, selindex)]

    def move_selection(self, direction: int):
        self.selected_line = navigate_list(self.lines, self.selected_line, direction)

    def cursesloop(self, win):

        while True:
            win.clear()
            height, width = win.getmaxyx()

            # ==== RENDER ==== #

            # header
            header = self.basedir + ':  ' + ' vs '.join([
                p + ' (' + n + ')'
                for n, p in self.dirs_to_compare
            ])
            hexes.fill_line(win, 0, 0, width, curses.A_REVERSE)
            win.addnstr(0, 0, header, width, curses.A_REVERSE)

            # list of differences #
            def render_line(y: int, l: Line, is_sel: bool):

                linechar = '·'

                attr = curses.A_REVERSE if is_sel else 0
                hexes.fill_line(win, y, 0, width, attr, char=linechar)
                win.addnstr(y, 0, l.displayname + ' ', width, attr)
                win.addnstr(y, width - 21, (' ' + ','.join(l.info.differences) + ' ').rjust(20, linechar), 20, attr)

            iutil.render_list(win, self.lines, self.selected_line, 1, height - 3, width, render_line)

            # status bar / legend #
            if self.temp_status_bar:
                status = self.temp_status_bar
            else:
                status = '[↑|↓] Select  [F5] Refresh  '
                if self.selected_line:
                    for label, cmd in self.selected_line.info.actions:
                        status += '[' + label[0] + ']' + label[1:] + '  '
            hexes.fill_line(win, height - 1, 0, width - 1, curses.A_REVERSE)
            win.addnstr(height - 1, 0, status, width - 1, curses.A_REVERSE)
            self.temp_status_bar = None

            win.move(height - 1, width - 1)
            win.refresh()

            # ==== INPUT ==== #

            # get user input
            ch = win.getch()
            try:
                char = chr(ch)
            except ValueError:
                char = None

            if char == 'q':
                return
            elif ch == curses.KEY_RESIZE:
                pass

            elif ch == curses.KEY_F5:
                self.compare()

            # navigate list
            elif ch == curses.KEY_DOWN:  self.move_selection(1)
            elif ch == curses.KEY_UP:    self.move_selection(-1)
            elif ch == curses.KEY_NPAGE: self.move_selection(10)
            elif ch == curses.KEY_PPAGE: self.move_selection(-10)
            elif ch == curses.KEY_HOME:  self.selected_line = self.lines[0]
            elif ch == curses.KEY_END:   self.selected_line = self.lines[-1]

            else:

                # check actions of selected item
                handled = False
                if self.selected_line:
                    for label, cmd in self.selected_line.info.actions:
                        if char == label[0].lower():

                            if callable(cmd):
                                cmd()
                                self.compare()
                                handled = True
                                break
                            else:

                                def run_outside_curses():

                                    # some commands open new graphical windows
                                    newwindow = cmd[0] == 'meld'

                                    # get approval if required
                                    if newwindow or cmd[0] in ['cat', 'diff']:
                                        approval = True
                                    else:
                                        print('Going to run command:')
                                        for c in cmd:
                                            print(c)
                                        approval = input('Run y/n?') == 'y'
                                        if not approval:
                                            print('Aborted!')

                                    # run the command if approval gained
                                    if approval:
                                        if newwindow:
                                            print('Close ' + cmd[0] + ' window to return to main interface...')
                                        subprocess.run(cmd)

                                    # let user read the output before returning
                                    if not newwindow:
                                        print('Press enter to return to main interface...')
                                        input()
                                    print('------------------------------')

                                    # refresh
                                    self.compare()

                                return run_outside_curses

                # ???
                if not handled:
                    self.temp_status_bar = 'Unknown key ' + str(ch) + ' (' + char + ')'
