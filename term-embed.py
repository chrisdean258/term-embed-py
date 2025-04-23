#!/usr/bin/env python3

import pty
import sys
import os
import select
import tty


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
        else:
            args = b';'.join(str(a).encode() for a in args)
            val = b'\033[' + args + spec
            b']'
            # print("\nNot Handling:", val)
            self.tty.write(val)
            self.tty.flush()
            # os.write(self.pty, val)

    def inc_row(self):
        if self._cursor_r < self.nrows:
            self._cursor_r += 1

    def start(self):
        self.child_pid, self.pty = pty.fork()
        try:
            return self._start()
        finally:
            os.close(self.pty)

    def _start(self):
        self.child_pid, self.pty = pty.fork()
        if self.child_pid == 0:
            os.execlp("/bin/bash", "/bin/bash", "-i")
            sys.exit(1)

        ipt = open(sys.stdin.fileno(), "r+b")
        tty.setraw(ipt.fileno())
        ipt.flush()
        os.set_blocking(ipt.fileno(), False)

        while True:
            read, _, _ = select.select([self.pty, ipt], [], [])
            for row in read:
                if row == self.pty:
                    blocks = []
                    while select.select([self.pty], [], [], 0)[0]:
                        blocks.append(os.read(self.pty, 1024))
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
                        elif c.startswith(b"\r"):
                            self._cursor_c = 0
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


def main():
    t = Terminal(open(sys.stdout.fileno(), "wb"), 1, 1, 100, 100)
    t.start()
    return 0


if __name__ == '__main__':
    sys.exit(main())
