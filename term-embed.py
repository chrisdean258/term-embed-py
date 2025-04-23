#!/usr/bin/env python3

import pty
import sys
import os
import select
import tty
import fcntl
import termios
import struct


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

    @property
    def cursor(self):
        return (self._cursor_r, self._cursor_c)

    @cursor.setter
    def cursor(self, cursor):
        self._cursor_r, self._cursor_c = cursor

    @property
    def term_cursor(self):
        return (self._cursor_r + self.row, self._cursor_c + self.col)

    @staticmethod
    def parse_cs(seq):
        if not seq.startswith(b"\033["):
            b']'
            return None, [], b''
        p = 2
        nums = []
        while p < len(seq):
            v = 0
            while seq and b'0' <= seq[p:p+1] <= b'9':
                v *= 10
                v += seq[p] - ord(b'0')
                p += 1
            nums.append(v)
            if p >= len(seq):
                break
            if seq[p:p+1] == b';':
                p += 1
                continue
            if p < len(seq):
                return seq[p:p+1], nums, seq[p + 1:]
            break
        return None, [], b''

    def handle_cs(self, spec, args):
        if spec == b'n' and args and args[0] == 6:
            a = b"\033[%d;%dR" % self.cursor
            b']'
            os.write(self.pty, a)
        elif spec == b'H' and len(args) == 2:
            r, c = args
            val = b'\x1b[%d;%dH' % (r + self.row, c + self.col)
            b']'
            self.tty.write(val)
            self.tty.flush()
        else:
            args = b';'.join(str(a).encode() for a in args)
            val = b'\033[' + args + spec
            b']'
            self.tty.write(val)
            self.tty.flush()

    def inc_row(self):
        if self._cursor_r < self.nrows:
            self._cursor_r += 1

    def start(self):
        self.pty, child = pty.openpty()
        print("hi")
        self.child_pid = os.fork()
        if self.child_pid == 0:
            os.dup2(child, 0)
            os.dup2(child, 1)
            os.dup2(child, 2)
            winsize = struct.pack("HH", self.nrows, self.ncols)
            fcntl.ioctl(self.pty, termios.TIOCSWINSZ, winsize)
            os.close(self.pty)
            os.close(child)
            os.execlp("/bin/bash", "/bin/bash", "-i")
            sys.exit(1)
        ipt = open(sys.stdin.fileno(), "rb")
        tty.setraw(ipt.fileno())
        os.set_blocking(ipt.fileno(), False)
        try:
            return self._start(ipt)
        finally:
            os.close(self.pty)

    def _start(self, ipt):
        while check_pid(self.child_pid):
            read, _, _ = select.select([self.pty, ipt], [], [])
            for row in read:
                if row == self.pty:
                    blocks = []
                    while select.select([self.pty], [], [], 0)[0]:
                        try:
                            blocks.append(os.read(self.pty, 1024))
                        except IOError:
                            break

                    chs = b''.join(blocks)
                    i = 0
                    while i < len(chs):
                        c = chs[i:]
                        if c.startswith(b'\x1b'):
                            control, args, rest = Terminal.parse_cs(c)
                            if control:
                                chs, i = rest, 0
                                self.handle_cs(control, args)
                                continue
                        elif c.startswith(b"\n"):
                            self._cursor_c = 0
                            self.inc_row()
                            # self.tty.write(b'\x1b[%d;%dH' % self.term_cursor)
                            continue

                        elif c.startswith(b"\r"):
                            self._cursor_c = 0
                            # self.tty.write(b'\x1b[%d;%dH' % self.term_cursor)
                            continue
                        else:
                            self._cursor_c += 1
                            if self._cursor_c >= self.ncols:
                                self.inc_row()
                                self._cursor_c = 0
                        self.tty.write(c[:1])
                        self.tty.flush()
                        i += 1
                if row == ipt:
                    c = ipt.read(1024)
                    os.write(self.pty, c)
        os.wait()


def check_pid(pid):
    """ Check For the existence of a unix pid. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def get_terminal_size(fd):
    try:
        rows, columns = os.get_terminal_size()
        return rows, columns
    except OSError:
        return 80, 25

    try:
        s = struct.pack("HHHH", 0, 0, 0, 0)
        res = fcntl.ioctl(fd, termios.TIOCGWINSZ, s)
        rows, columns, _, _ = struct.unpack("HHHH", res)
        return columns, rows
    except OSError:
        return 80, 25


def main():
    rows, cols = get_terminal_size(sys.stdout.fileno())
    print(rows, cols)
    t = Terminal(open(sys.stdout.fileno(), "wb"), 10, 10, rows - 20, cols - 20)
    t.start()
    return 0


if __name__ == '__main__':
    sys.exit(main())
