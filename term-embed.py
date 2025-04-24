#!/usr/bin/env python3

import pty
import sys
import os
import select
import tty
import termios
import struct
import fcntl

log = open("log", "w")


class Terminal:
    def __init__(self, tty, row, col, nrows, ncols):
        self.row = row
        self.col = col
        self.nrows = nrows
        self.ncols = ncols
        self.tty = tty
        self._cursor_r = 0
        self._cursor_c = 0
        self.child_pid = None
        self.pty = None
        self.screen = [b' '] * (nrows * ncols)
        self.normal_screen_contents = None
        self.normal_screen_cursor = None
        self.scroll_region = (1, nrows)

    @property
    def cursor(self):
        return (self._cursor_r, self._cursor_c)

    @cursor.setter
    def cursor(self, cursor):
        self._cursor_r, self._cursor_c = cursor
        self.move_cursor()

    @property
    def term_cursor(self):
        return (self._cursor_r + self.row, self._cursor_c + self.col)

    @staticmethod
    def parse_cs(seq):
        if not seq.startswith(b"\033["):
            b']'
            return None, [], b'', False
        extra = b''
        nums = []
        if seq[2:3] in b'?<>=!':
            extra = seq[2:3]

        p = 2 + len(extra)
        while p < len(seq):
            v = 0
            digit = False
            while p < len(seq) and b'0' <= seq[p:p+1] <= b'9':
                digit = True
                v *= 10
                v += seq[p] - ord(b'0')
                p += 1
            if digit:
                nums.append(v)
            if p >= len(seq):
                break
            if seq[p:p+1] == b';':
                p += 1
                continue
            if p < len(seq):
                return seq[p:p+1], nums, seq[p + 1:], extra
            break
        return None, [], b'', False

    def passthrough(self, spec, args, private):
        args = b';'.join(str(a).encode() for a in args)
        val = b'\033[' + (b'?' if private else b'') + args + spec
        self.tty.write(val)

    def handle_cs(self, spec, args, private):
        a = b';'.join(str(a).encode() for a in args)
        val = b'\033[' + (b'?' if private else b'') + a + spec
        print("logging:", val, file=log, flush=True)
        if spec in b'A':  # Move Cursor up
            self._cursor_r = max(self._cursor_c - (args + [1])[0], 0)
            self.move_cursor()
        elif spec == b'B' and len(args) == 2:  # Move cursor Down
            self._cursor_c = min(self._cursor_c + (args + [1])[0], self.nrows - 1)  # noqa:E501
            self.move_cursor()
        if spec == b'C':
            self._cursor_c = min(self._cursor_c + (args + [1])[0], self.ncols)
            self.move_cursor()
        elif spec == b'D' and len(args) == 2:  # Move cursor left
            self._cursor_c = max(self._cursor_c - (args + [1])[0], 0)
            self.move_cursor()
        elif spec == b'H':
            row_1, col_1 = (args + [0, 0])[:2]
            self.cursor = (row_1 - 1, col_1 - 1)
        elif spec == b'h' and args[0:1] == [1049]:
            self.normal_screen_contents = self.screen
            self.normal_screen_cursor = self.cursor
            self.screen = [b' '] * (self.nrows * self.nrows)
            self.cursor = (0, 0)
            self.redraw()
        elif spec == b'h':
            self.passthrough(spec, args, private)
        elif spec == b'J':
            # if args and args[0] == 2: # this is right and need update
            self.screen = [b' '] * (self.ncols * self.nrows)
            self.redraw()
            self.cursor = (0, 0)
        elif spec == b'K':
            cursor = self.cursor
            if args and args[0] == 1:  # erase to left
                start = self._cursor_r * self.ncols
                end = self._cursor_r * self.ncols + self._cursor_c
            elif args and args[0] == 2:  # erase full line
                start = self._cursor_r * self.ncols
                end = start + self.ncols
                cursor = (self._cursor_r, 0)
            else:  # Erase to right
                start = self._cursor_r * self.ncols + self._cursor_c
                end = (self._cursor_r + 1) * self.ncols
            self.screen[start:end] = [b' '] * (end - start)
            self.tty.write(b' ' * (end - start))
            self.cursor = cursor
            self.tty.flush()
        elif spec == b'l' and args[0:1] == [1049] and private:
            self.screen = self.normal_screen_contents
            self.normal_screen_contents = None
            self.cursor = self.normal_screen_cursor
            self.redraw()
        elif spec == b'L':
            nlines = (args + [1])[0]
            start, end = self.scroll_region
            self.scroll_region = 0, self._cursor_r
            self.scroll_screen(-nlines)
            self.scroll_region = start, end

        elif spec == b'l':
            self.passthrough(spec, args, private)
        elif spec == b'm':  # Color
            self.passthrough(spec, args, private)
        elif spec == b'n' and args and args[0] == 6:  # Cursor position
            a = b"\033[%d;%dR" % (self._cursor_r + 1, self._cursor_c + 1)
            print("logging response:", a, file=log, flush=True)
            os.write(self.pty, a)
        elif spec == b'r':
            bottom, top = (args or [1, self.nlines])[:2]
            self.scroll_region = (bottom, top)
        elif spec == b'S':
            nlines = (args or [1])[0]
            self.scroll_screen(-nlines)
        elif spec == b'T':
            nlines = (args or [1])[0]
            self.scroll_screen(nlines)
        elif spec == b'>' or spec == b'=':  # no exactly sure here. numpad?
            self.passthrough(spec, args, private)
        else:
            self.passthrough(spec, args, private)
            args = b';'.join(str(a).encode() for a in args)
            val = b'\033[' + (b'?' if private else b'') + args + spec
            print("skipping", val, file=log, flush=True)

    def redraw(self, first=0, last=None):
        if last is None:
            last = self.ncols
        HIDE_CURSOR = b'\x1b[?25l'
        SHOW_CURSOR = b'\x1b[?12l\x1b[?25h'
        cursor = self.cursor
        ncols = self.ncols
        self.tty.write(HIDE_CURSOR)
        for i in range(first, last - 1):
            self.cursor = (i, 0)
            content = b''.join(self.screen[ncols * i:ncols * (i + 1)])
            self.tty.write(content)
        self.cursor = cursor
        self.tty.write(SHOW_CURSOR)
        self.tty.flush()

    def scroll_screen(self, nlines=1):
        assert len(self.screen) == self.ncols * self.nrows
        cursor = self.cursor
        first_1, last_1 = self.scroll_region
        first, last = first_1 - 1, last_1 - 1
        region = self.screen[self.ncols * first:self.ncols * (last)]
        size = len(region)
        buff = [b' '] * (abs(nlines) * self.ncols)
        if nlines > 0:
            region = (region + buff)[-size:]
        elif nlines < 0:
            region = (buff + region)[:size]
        self.screen[self.ncols * first:self.ncols * (last)] = region
        self.redraw()
        self.cursor = cursor
        assert len(self.screen) == self.ncols * \
            self.nrows, f"{len(self.screen)} {nlines}"

    def write_out(self, char):
        max_size = self.nrows * self.ncols
        idx = self._cursor_r * self.ncols + self._cursor_c
        if idx >= max_size:
            self.scroll_screen()
            idx -= self.ncols
        self.screen[idx] = char
        self.tty.write(char)
        self._cursor_c += 1
        if self._cursor_c >= self.ncols:
            self.inc_row()
            self._cursor_c = 0

    def inc_row(self):
        if self._cursor_r < self.nrows:
            self._cursor_r += 1
        else:
            self.scroll_screen()

    def move_cursor(self):
        MOVE_CURSOR = b'\x1b[%d;%dH'
        self.tty.write(MOVE_CURSOR % (self._cursor_r + self.row, self._cursor_c + self.col))  # noqa:E501

    def start(self):
        self.child_pid, self.pty = pty.fork()
        try:
            self._start()
        except OSError:
            pass

    def _start(self):
        self.move_cursor()
        self.child_pid, self.pty = pty.fork()
        if self.child_pid == 0:
            os.environ["ROWS"] = str(self.nrows)
            os.environ["COLUMNS"] = str(self.ncols)
            os.environ["PS1"] = '$ '
            os.execlp("/bin/sh", "/bin/sh", "-i")
            sys.exit(1)

        stdin = sys.stdin.buffer
        tty.setraw(stdin.fileno())
        stdin.flush()

        while os.waitpid(self.child_pid, os.WNOHANG) == (0, 0):
            read, _, _ = select.select([self.pty, stdin], [], [])
            for row in read:
                if row == self.pty:
                    blocks = []
                    while select.select([self.pty], [], [], 0)[0] and (c := os.read(self.pty, 1024)):  # noqa:E501
                        blocks.append(c)
                    chs = b''.join(blocks)
                    i = 0
                    while i < len(chs):
                        c = chs[i:]
                        i += 1
                        if c.startswith(b'\x1b'):
                            control, args, rest, private = Terminal.parse_cs(c)
                            if control:
                                chs, i = rest, 0
                                self.handle_cs(control, args, private)
                                continue
                        elif c.startswith(b"\n"):
                            self._cursor_c = 0
                            self.inc_row()
                            self.move_cursor()
                            continue
                        elif c.startswith(b"\r"):
                            self._cursor_c = 0
                            self.move_cursor()
                            continue
                        elif c.startswith(b"\b"):
                            self._cursor_c = max(self._cursor_c - 1, 0)
                            self.move_cursor()
                            self.tty.flush()
                            continue
                        else:
                            try:
                                if not c[:1].decode().isprintable():
                                    print("Not handling:", c[:5], file=log)
                            except Exception:
                                print("Not handling:", c[:5], file=log)
                            print("logging:", c[:1], file=log, flush=True)
                            self.write_out(c[:1])
                    self.tty.flush()
                if row == stdin:
                    os.set_blocking(stdin.fileno(), False)
                    c = stdin.read(1024)
                    os.set_blocking(stdin.fileno(), True)
                    print("input log:", c, file=log, flush=True)
                    os.write(self.pty, c)


def get_terminal_size(fd):
    try:
        rows, columns = os.get_terminal_size()
        return rows, columns
    except OSError:
        pass

    try:
        s = struct.pack("HHHH", 0, 0, 0, 0)
        res = fcntl.ioctl(fd, termios.TIOCGWINSZ, s)
        rows, columns, _, _ = struct.unpack("HHHH", res)
        return columns, rows
    except OSError:
        return 80, 25


def main():
    sys.stdout.write('\x1b[?1049h')
    sys.stdout.write('\033[2J')
    sys.stdout.flush()
    print('\x1b[;H' + "+\n" * 8 + 'x' * 8 + "+" + '-' * 100 + "+")
    for i in range(25):
        print(8 * 'x' + "|" + ' ' * 100 + "|")
    print(8*'x' + "+" + '-' * 100 + "+", flush=True)
    t = Terminal(sys.stdout.buffer, 10, 10, 25, 100)
    old_settings = termios.tcgetattr(1)
    tty.setraw(0)
    try:
        t.start()
    finally:
        sys.stdout.write('\x1b[r')
        sys.stdout.write('\x1b[?1049l')
        sys.stdout.flush()
        termios.tcsetattr(1, termios.TCSADRAIN, old_settings)
        tty.setcbreak(0)

    return 0


if __name__ == '__main__':
    sys.exit(main())
