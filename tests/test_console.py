"""Pipe input must cancel without a blocked input thread or leaked stdin flags."""

import asyncio
import os
import sys

import pytest

from pragyantra.inputs.console import ConsoleInput


def test_cancelling_console_read_restores_original_descriptor(monkeypatch):
    read_fd, write_fd = os.pipe()
    with os.fdopen(read_fd, "r") as pipe, os.fdopen(write_fd, "w"):
        monkeypatch.setattr(sys, "stdin", pipe)
        original = os.get_blocking(pipe.fileno())

        async def scenario():
            async with ConsoleInput() as console:
                assert not os.get_blocking(pipe.fileno())
                task = asyncio.create_task(console.read())
                await asyncio.sleep(0)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            assert os.get_blocking(pipe.fileno()) == original
            assert not pipe.closed

        asyncio.run(scenario())
