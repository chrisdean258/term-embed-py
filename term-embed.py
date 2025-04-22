#!/usr/bin/env python3

import pty
import sys
import os
import select


class Terminal:
    def __init__(self, tty, r, c, h, w):
        self.r = r
        self.r = r
        self.h = h
        self.w = w
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
        if not seq.startswith(b"\033"):
            return None, [], b''
        p = 1
        nums = []
        while p < len(seq):
            v = 0
            while seq and b'0' <= seq[0:1] <= b'9':
                v *= 10
                v += seq[p]
                p += 1
            nums.append(v)
            if seq[p] == b';':
                p += 1
                continue
            if p < len(seq):
                return seq[p], nums, seq[p + 1:]
            return None, [], b''

    def handle_cs(self, spec, args):
        if spec == b'n' and args and args[0] == 6:
            os.write(self.pty, b'\033[%d;%dR' % self.cursor)
            b']'

    def inc_row(self):
        if self._cursor_r < self.h:
            self._cursor_r += 1

    def start(self):
        self.child_pid, self.pty = pty.fork()
        if self.child_pid == 0:
            os.execlp("/bin/bash", "/bin/bash", "-i")
            sys.exit(1)

        ipt = open(sys.stdin.fileno(), "rb")
        os.set_blocking(ipt.fileno(), False)

        while True:
            read, _, _ = select.select([self.pty, ipt], [], [])
            for r in read:
                if r == self.pty:
                    chs = os.read(self.pty, 100)
                    i = 0
                    while i < len(chs):
                        c = chs[i:]
                        if c.startswith(b'\x1b'):
                            control, args, rest = Terminal.parse_cs(c)
                            if control:
                                chs, i = rest, 0
                                self.handle_cs(control, args)
                        elif c.startswith(b"\n"):
                            self._cursor_c = 0
                            self.inc_row()
                        elif c.startswith(b"\r"):
                            self._cursor_c = 0
                        else:
                            self._cursor_c += 1
                            if self._cursor_c >= self.w:
                                self.inc_row()
                                self._cursor_c = 0
                            self.tty.write(c)
                            self.tty.flush()
                        i += 1
                if r == ipt:
                    c = ipt.read(1024)
                    os.write(self.pty, c)
        os.wait()


def main():
    t = Terminal(open(sys.stdout.fileno(), "wb"), 1, 1, 100, 100)
    t.start()
    return 0


if __name__ == '__main__':
    sys.exit(main())
