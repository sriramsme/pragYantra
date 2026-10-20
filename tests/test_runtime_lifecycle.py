"""Resource ownership under errors and cancellation, without actual hardware."""

import asyncio
from collections.abc import AsyncIterator

import pytest

from pragyantra.application.behavior import DescribeOnTouch
from pragyantra.application.models import ContextResponse, ObservationEvent
from pragyantra.application.runtime import AssistantRuntime
from pragyantra.inputs.simulated import SimulatedInput, visual_context_demo
from pragyantra.outputs.simulated import RecordingOutput


def test_input_closes_when_output_startup_fails():
    class FailedOutput(RecordingOutput):
        async def __aenter__(self):
            raise OSError("Output unavailable")

    source = visual_context_demo()
    output = FailedOutput()
    runtime = AssistantRuntime(DescribeOnTouch(), now=source.now)
    with pytest.raises(OSError, match="Output unavailable"):
        asyncio.run(runtime.run(source, output))
    assert source.closed


def test_resources_close_and_output_error_propagates():
    class FailedOutput(RecordingOutput):
        async def emit(self, response: ContextResponse) -> None:
            raise OSError("Output disconnected")

    source = visual_context_demo()
    output = FailedOutput()
    runtime = AssistantRuntime(DescribeOnTouch(), now=source.now)
    with pytest.raises(OSError, match="Output disconnected"):
        asyncio.run(runtime.run(source, output))
    assert source.closed and output.closed


def test_resources_close_and_input_error_propagates():
    class FailedInput(SimulatedInput):
        async def __aiter__(self) -> AsyncIterator[ObservationEvent]:
            async for event in super().__aiter__():
                yield event
            raise OSError("Input disconnected")

    source = FailedInput([])
    output = RecordingOutput()
    runtime = AssistantRuntime(DescribeOnTouch(), now=source.now)
    with pytest.raises(OSError, match="Input disconnected"):
        asyncio.run(runtime.run(source, output))
    assert source.closed and output.closed


def test_cancellation_closes_resources_without_being_swallowed():
    async def scenario():
        class BlockingOutput(RecordingOutput):
            def __init__(self):
                super().__init__()
                self.entered_emit = asyncio.Event()

            async def emit(self, response: ContextResponse) -> None:
                self.entered_emit.set()
                await asyncio.Event().wait()

        source = visual_context_demo()
        output = BlockingOutput()
        runtime = AssistantRuntime(DescribeOnTouch(), now=source.now)
        task = asyncio.create_task(runtime.run(source, output))
        await asyncio.wait_for(output.entered_emit.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert source.closed and output.closed

    asyncio.run(scenario())
