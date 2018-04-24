import curses

def render_list(win, lst, sel, listStart, listHeight, width, render_entry):
    if listHeight < 0: return

    # selected index
    curIndex = 0 if sel == None else lst.index(sel)

    overflow = len(lst) - listHeight

    # scroll
    offset = curIndex - int(listHeight / 2)
    if offset < 0: offset = 0
    if offset > overflow: offset = overflow
    if overflow < 0: offset += int(-overflow/2)

    # render in box
    for i in range(0, listHeight):

        io = offset + i
        if io < 0 or io >= len(lst):
            continue

        render_entry(i + listStart, lst[io], lst[io] == sel)

    # cursor indicator
    if sel != None:
        cursorText = '#' + str(curIndex) + '/' + str(len(lst))
        win.addnstr(listStart, width-len(cursorText)-1, cursorText, len(cursorText), curses.A_REVERSE | curses.A_DIM)

    #if offset > 0: win.addnstr(listStart, width-1, '↑', 1, curses.A_DIM)
    #if offset < overflow: win.addnstr(listStart+listHeight-1, width-1, '↓', 1, curses.A_DIM)

    # scrollbar
    if overflow > 0 and listHeight > 2:

        for sy in range(0, listHeight):
            win.addnstr(listStart + sy, width-1, ' ', 1, curses.A_REVERSE | curses.A_DIM)

        progress = offset / overflow

        y = round(progress * (listHeight-1))
        if y == 0 and progress != 0: y = 1
        if y == listHeight-1 and progress != 1: y = listHeight-2

        win.addnstr(listStart + y, width-1, '↕', 1, curses.A_REVERSE | curses.A_DIM)
