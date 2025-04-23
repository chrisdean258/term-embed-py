#!/usr/bin/env python3

import pty
import sys
import os
import select
import tty
<<<<<<< Updated upstream
import fcntl
import termios
import struct
=======
import termios
>>>>>>> Stashed changes


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
<<<<<<< Updated upstream
            return None, [], b''
        p = 2
=======
            return None, [], b'', False
        saw_question = False
>>>>>>> Stashed changes
        nums = []
        if seq[2:3] == b'?':
            saw_question = True

        p = 2 + saw_question
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
<<<<<<< Updated upstream
                return seq[p:p+1], nums, seq[p + 1:]
            break
        return None, [], b''
=======
                return seq[p:p+1], nums, seq[p + 1:], saw_question
            break
        return None, [], b'', False
>>>>>>> Stashed changes

    def handle_cs(self, spec, args, private):
        if spec == b'n' and args and args[0] == 6:
            a = b"\033[%d;%dR" % self.cursor
<<<<<<< Updated upstream
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
=======
            os.write(self.pty, a)
        elif spec == b'h' and args[0:1] == [1049] and private:
            # enter alternate buffer
            pass
        elif spec == b'l' and args[0:1] == [1049] and private:
            # leav alternate buffer
            pass

        elif spec == b'H' and len(args) == 2:
            self.cursor = args
            self.move_cursor()
        elif spec == b'C' and len(args) == 2:
            self._cursor_c = min(self._cursor_c + args[0], self.ncols)
            self.move_cursor()
        elif spec == b'D' and len(args) == 2:
            self._cursor_c = max(self._cursor_c - args[0], 0)
            self.move_cursor()
        elif spec == b'm':
            args = b';'.join(str(a).encode() for a in args)
            val = b'\033[' + args + spec
            self.tty.write(val)
        else:
            args = b';'.join(str(a).encode() for a in args)
            val = b'\033[' + args + spec
            print("skipping", val)
            self.tty.write(val)
            # self.tty.flush()
            # os.write(self.pty, val)
>>>>>>> Stashed changes

    def inc_row(self):
        if self._cursor_r < self.nrows:
            self._cursor_r += 1

    def move_cursor(self):
        MOVE_CURSOR = b'\x1b[%d;%dH'
        self.tty.write(MOVE_CURSOR % (self._cursor_r + self.row, self._cursor_c + self.col))  # noqa:E501

    def start(self):
<<<<<<< Updated upstream
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
=======
        self.child_pid, self.pty = pty.fork()
        self._start()
        os.wait()

    def _start(self):
        self.move_cursor()
        self.child_pid, self.pty = pty.fork()
        if self.child_pid == 0:
            os.environ["ROWS"] = str(self.nrows)
            os.environ["COLUMNS"] = str(self.ncols)
            os.environ["PS1"] = '$ '
            os.execlp("/bin/sh", "/bin/sh", "-i")
            sys.exit(1)

        stdin = open(sys.stdin.fileno(), "rb")
        tty.setraw(stdin.fileno())
        stdin.flush()
        os.set_blocking(stdin.fileno(), False)

        while True:
            read, _, _ = select.select([self.pty, stdin], [], [])
>>>>>>> Stashed changes
            for row in read:
                if row == self.pty:
                    blocks = []
                    while select.select([self.pty], [], [], 0)[0]:
                        try:
                            blocks.append(os.read(self.pty, 1024))
<<<<<<< Updated upstream
                        except IOError:
                            break

                    chs = b''.join(blocks)
=======
                        except OSError:
                            return
                    chs = b'!!'.join(blocks)
>>>>>>> Stashed changes
                    i = 0
                    while i < len(chs):
                        c = chs[i:]
                        i += 1
                        if c.startswith(b'\x1b'):
                            control, args, rest, private = Terminal.parse_cs(c)
                            if control:
                                chs, i = rest, 0
<<<<<<< Updated upstream
                                self.handle_cs(control, args)
=======
                                self.handle_cs(control, args, private)
>>>>>>> Stashed changes
                                continue
                        elif c.startswith(b"\n"):
                            self._cursor_c = 0
                            self.inc_row()
<<<<<<< Updated upstream
                            # self.tty.write(b'\x1b[%d;%dH' % self.term_cursor)
                            continue

                        elif c.startswith(b"\r"):
                            self._cursor_c = 0
                            # self.tty.write(b'\x1b[%d;%dH' % self.term_cursor)
=======
                            self.move_cursor()
                            continue
                        elif c.startswith(b"\r"):
                            self._cursor_c = 0
                            self.move_cursor()
>>>>>>> Stashed changes
                            continue
                        else:
                            self._cursor_c += 1
                            if self._cursor_c >= self.ncols:
                                self.inc_row()
                                self._cursor_c = 0
<<<<<<< Updated upstream
                        self.tty.write(c[:1])
                        self.tty.flush()
                        i += 1
                if row == ipt:
                    c = ipt.read(1024)
                    os.write(self.pty, c)
        os.wait()
=======
                            self.tty.write(c[:1])
                        self.tty.flush()
                if row == stdin:
                    try:
                        c = stdin.read(1024)
                        os.write(self.pty, c)
                    except OSError:
                        return
>>>>>>> Stashed changes


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
<<<<<<< Updated upstream
    rows, cols = get_terminal_size(sys.stdout.fileno())
    print(rows, cols)
    t = Terminal(open(sys.stdout.fileno(), "wb"), 10, 10, rows - 20, cols - 20)
    t.start()
=======
    sys.stdout.write('\x1b[?1049h')
    sys.stdout.write('\033[2J')
    sys.stdout.flush()
    t = Terminal(open(sys.stdout.fileno(), "wb"), 10, 10, 25, 100)
    old_settings = termios.tcgetattr(0)
    tty.setraw(sys.stdin.fileno())
    try:
        t.start()
    finally:
        sys.stdout.write('\x1b[?1049l')
        sys.stdout.flush()
        tty.setcbreak(sys.stdin.fileno())
        termios.tcsetattr(0, termios.TCSADRAIN, old_settings)

>>>>>>> Stashed changes
    return 0


if __name__ == '__main__':
    sys.exit(main())
