"""Cancellable Linux terminal/pipe input, without an unjoinable input() thread."""

import asyncio
import os
import stat
import sys


class ConsoleInput:
    def __init__(self) -> None:
        self._reader = None
        self._transport = None
        self._pipe = None
        self._blocking = None
        self._file = False

    async def __aenter__(self):
        self._file = stat.S_ISREG(os.fstat(sys.stdin.fileno()).st_mode)
        if self._file:
            return self
        self._pipe = os.fdopen(os.dup(sys.stdin.fileno()), "rb", buffering=0)
        self._blocking = os.get_blocking(self._pipe.fileno())
        self._reader = asyncio.StreamReader(limit=16384)
        protocol = asyncio.StreamReaderProtocol(self._reader)
        try:
            self._transport, _ = await asyncio.get_running_loop().connect_read_pipe(
                lambda: protocol, self._pipe
            )
        except BaseException:
            self._restore()
            raise
        return self

    def _restore(self):
        if self._pipe is not None and not self._pipe.closed:
            os.set_blocking(self._pipe.fileno(), self._blocking)
        if self._transport is not None:
            self._transport.close()
        elif self._pipe is not None:
            self._pipe.close()

    async def read(self) -> str | None:
        if sys.stdin.isatty():
            print("You: ", end="", file=sys.stderr, flush=True)
        if self._file:
            line = sys.stdin.buffer.readline(16385)
        else:
            try:
                line = await self._reader.readline()
            except ValueError as exc:
                raise ValueError("Input line exceeds 16 KiB") from exc
        if len(line) > 16384:
            raise ValueError("Input line exceeds 16 KiB")
        if not line:
            return None
        try:
            return line.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ValueError("Console input must be UTF-8") from exc

    async def __aexit__(self, *args):
        self._restore()
