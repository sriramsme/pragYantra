"""Behavior and timing checks using a logical clock, without devices or APIs."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from pragyantra.application.behavior import DescribeOnTouch
from pragyantra.application.models import (
    ContextStatus,
    ObservationEvent,
    TouchObservation,
    VisualObservation,
)
from pragyantra.application.runtime import AssistantRuntime
from pragyantra.application.world_state import WorldState
from pragyantra.inputs.simulated import SimulatedInput, visual_context_demo
from pragyantra.outputs.simulated import RecordingOutput


def at(seconds: float) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)


def test_touch_without_visual_context_is_unavailable():
    response = DescribeOnTouch().respond(
        WorldState(), TouchObservation("touch", at(0)), at=at(0)
    )
    assert response.status is ContextStatus.UNAVAILABLE
    assert response.visual is None
    assert response.visual_age is None


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (0, ContextStatus.CURRENT),
        (5, ContextStatus.CURRENT),
        (5.001, ContextStatus.STALE),
    ],
)
def test_freshness_boundary_uses_acquisition_time(age, expected):
    state = WorldState()
    visual = VisualObservation("camera", at(0), "A mug on a desk.")
    state.observe(visual)
    response = DescribeOnTouch().respond(
        state, TouchObservation("touch", at(age)), at=at(age)
    )
    assert response.status is expected
    assert response.visual is visual
    assert response.visual_age == timedelta(seconds=age)
    if expected is ContextStatus.CURRENT:
        assert visual.description in response.text
    else:
        assert visual.description not in response.text


def test_older_and_equal_time_results_do_not_replace_newer_context():
    state = WorldState()
    current = VisualObservation("camera", at(2), "Current scene.")
    assert state.observe(current)
    assert not state.observe(VisualObservation("camera", at(1), "Delayed old scene."))
    assert not state.observe(
        VisualObservation("camera", at(2), "Duplicate frame result.")
    )
    assert state.visual is current


def test_newer_acquisition_replaces_context():
    state = WorldState()
    state.observe(VisualObservation("camera", at(0), "Previous scene."))
    latest = VisualObservation("camera", at(1), "New scene.")
    assert state.observe(latest)
    assert state.visual is latest


def test_demo_runs_complete_behavior_and_closes_resources():
    source = visual_context_demo(scene="A notebook.", started_at=at(0))
    output = RecordingOutput()
    runtime = AssistantRuntime(DescribeOnTouch(), now=source.now)
    asyncio.run(runtime.run(source, output))

    assert [response.status for response in output.responses] == [
        ContextStatus.UNAVAILABLE,
        ContextStatus.CURRENT,
        ContextStatus.STALE,
    ]
    current = output.responses[1]
    assert current.visual.description == "A notebook."
    assert current.visual_age == timedelta(seconds=2)
    assert current.trigger.source == "simulated.touch"
    assert output.responses[2].visual.description == "A notebook."
    assert runtime.state.visual.observed_at == at(1)
    assert source.closed and output.closed


def test_processing_delay_counts_toward_staleness():
    source = SimulatedInput(
        [
            ObservationEvent(VisualObservation("camera", at(0), "A scene."), at(0)),
            ObservationEvent(TouchObservation("touch", at(1)), at(1)),
        ]
    )
    output = RecordingOutput()
    runtime = AssistantRuntime(DescribeOnTouch(), now=lambda: at(10))
    asyncio.run(runtime.run(source, output))
    assert output.responses[0].status is ContextStatus.STALE
    assert output.responses[0].responded_at == at(10)


def test_delayed_inference_is_not_made_fresh_by_delivery():
    source = SimulatedInput(
        [
            ObservationEvent(
                VisualObservation("camera", at(0), "An old frame."), at(9)
            ),
            ObservationEvent(TouchObservation("touch", at(10)), at(10)),
        ]
    )
    output = RecordingOutput()
    runtime = AssistantRuntime(DescribeOnTouch(), now=source.now)
    asyncio.run(runtime.run(source, output))
    assert output.responses[0].status is ContextStatus.STALE
    assert output.responses[0].visual_age == timedelta(seconds=10)


@pytest.mark.parametrize("max_age", [timedelta(0), timedelta(seconds=-1)])
def test_invalid_freshness_threshold_is_rejected(max_age):
    with pytest.raises(ValueError, match="positive"):
        DescribeOnTouch(max_age)


def test_ambiguous_and_impossible_observation_times_are_rejected():
    with pytest.raises(ValueError, match="timezone"):
        TouchObservation("touch", datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="before acquisition"):
        ObservationEvent(TouchObservation("touch", at(1)), at(0))


def test_future_context_cannot_be_presented_as_current():
    state = WorldState()
    state.observe(VisualObservation("camera", at(2), "Future scene."))
    with pytest.raises(ValueError, match="ahead"):
        DescribeOnTouch().respond(state, TouchObservation("touch", at(0)), at=at(1))


def test_future_event_is_rejected_and_resources_close():
    source = SimulatedInput([ObservationEvent(TouchObservation("touch", at(2)), at(2))])
    output = RecordingOutput()
    runtime = AssistantRuntime(DescribeOnTouch(), now=lambda: at(0))
    with pytest.raises(ValueError, match="runtime clock"):
        asyncio.run(runtime.run(source, output))
    assert source.closed and output.closed


def test_receipt_order_is_checked_even_though_acquisition_can_be_out_of_order():
    source = SimulatedInput(
        [
            ObservationEvent(TouchObservation("touch", at(2)), at(2)),
            ObservationEvent(TouchObservation("touch", at(1)), at(1)),
        ]
    )
    output = RecordingOutput()
    runtime = AssistantRuntime(DescribeOnTouch(), now=source.now)
    with pytest.raises(ValueError, match="receipt time"):
        asyncio.run(runtime.run(source, output))
    assert len(output.responses) == 1
    assert source.closed and output.closed


def test_empty_input_completes_without_consulting_unstarted_clock():
    source = SimulatedInput([])
    output = RecordingOutput()
    asyncio.run(AssistantRuntime(DescribeOnTouch(), now=source.now).run(source, output))
    assert output.responses == ()
    assert source.closed and output.closed
