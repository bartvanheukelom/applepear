# coding=utf-8

import subprocess
import dirdiff
import curses
import iutil
import hexes

selLine = None
lines = []

def printNode(lines, prefix, name, info, depth = 0):

    if not info.differences: return

    if depth == 0: fullname = '.'
    elif prefix == '.': fullname = name
    else: fullname = prefix + '/' + name

    # recursively apply shortcuts
    displayname = fullname
    while (True):
        before = displayname
        for x, y in path_shortcuts:
            displayname = displayname.replace(x, y)
        if displayname == before: break

    # make more readable
    displayname = displayname.replace('/', ' / ')

    # add only real differences
    if info.differences != {'sub'}:
        lines += [{
            'displayname': displayname,
            'info': info
        }]

    # recurse
    if info.isDir:
        for mp in [info.subdirs, info.files]:
            for sn in sorted(mp.keys()):
                printNode(lines, fullname, sn, mp[sn], depth+1)

def compare():
    global lines, selLine

    # compare the dirs
    root = dirdiff.Compearison(compareDirs, compareDirNames, shouldInclude, add_ignore).root

    # flatten the result to a list of lines
    # preserve previous selection somewhat
    selindex = 0 if selLine is None else lines.index(selLine)
    lines = []
    printNode(lines, '', '', root)
    selLine = None if len(lines) == 0 else lines[min(len(lines)-1, selindex)]

def navigateList(lst, cur, direction):
    if cur == None: return None if len(lst) == 0 else lst[0]
    curIndex = lst.index(cur)
    return lst[(curIndex + direction) % len(lst)]

def moveSel(direction):
    global selLine
    selLine = navigateList(lines, selLine, direction)

def cursesloop(win):
    global lines, selLine

    tempStatusBar = None

    while True:
        win.clear()
        height, width = win.getmaxyx()


        ##### ==== RENDER ==== #####

        ### list of differences ###
        def render_line(y, l, is_sel):

            linechar = '·'

            attr = curses.A_REVERSE if is_sel else 0
            hexes.fill_line(win, y, 0, width, attr, char=linechar)
            win.addnstr(y, 0, l['displayname'] + ' ', width, attr)
            win.addnstr(y, width-21, (' ' + ','.join(l['info'].differences) + ' ').rjust(20, linechar), 20, attr)
        iutil.render_list(win, lines, selLine, 0, height-2, width, render_line)

        ### status bar / legend ###
        if tempStatusBar: status = tempStatusBar
        else:
            status = '[↑|↓] Select  [F5] Refresh  '
            if selLine:
                for label, cmd in selLine['info'].actions:
                    status += '[' + label[0] + ']' + label[1:] + '  '
        hexes.fill_line(win, height-1, 0, width-1, curses.A_REVERSE)
        win.addnstr(height-1, 0, status, width-1, curses.A_REVERSE)
        tempStatusBar = None

        win.move(height-1, width-1)
        win.refresh()


        ##### ==== INPUT ==== #####

        # get user input
        ch = win.getch()
        try:
            char = chr(ch)
        except ValueError:
            char = None

        if char == 'q': return
        elif ch == curses.KEY_RESIZE: pass

        elif ch == curses.KEY_F5: compare()

        # navigate list
        elif ch == curses.KEY_DOWN:  moveSel(1)
        elif ch == curses.KEY_UP:    moveSel(-1)
        elif ch == curses.KEY_NPAGE: moveSel(10)
        elif ch == curses.KEY_PPAGE: moveSel(-10)
        elif ch == curses.KEY_HOME:  selLine = lines[0]
        elif ch == curses.KEY_END:   selLine = lines[-1]

        else:

            # check actions of selected item
            handled = False
            if selLine:
                for label, cmd in selLine['info'].actions:
                    if char == label[0].lower():

                        if callable(cmd):
                            cmd()
                            compare()
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
                                compare()

                            return run_outside_curses

            # ???
            if not handled:
                tempStatusBar = 'Unknown key ' + str(ch) + ' (' + char + ')'

def run(compareDirs_, compareDirNames_, shouldInclude_, path_shortcuts_, add_ignore_):
    global compareDirs, compareDirNames, shouldInclude, path_shortcuts, add_ignore
    compareDirs = compareDirs_
    compareDirNames = compareDirNames_
    shouldInclude = shouldInclude_
    path_shortcuts = path_shortcuts_
    add_ignore = add_ignore_

    compare()
    while True:
        # loop can return an intermezzo function that should be invoked outside of curses
        intermezzo = curses.wrapper(cursesloop)
        if not intermezzo: break
        intermezzo()

