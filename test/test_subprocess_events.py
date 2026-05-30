import queue
import sys

from carbontracker.core.events import (
    ProcessExitedEvent,
    ProcessOutputEvent,
    ProcessStartedEvent,
)
from carbontracker.observers.providers.subprocess import SubprocessObserverThread


def drain(event_queue):
    events = []
    while not event_queue.empty():
        events.append(event_queue.get_nowait())
    return events


def test_subprocess_start_exit_and_output_events_reach_watch_sink():
    sink = queue.Queue()
    observer = SubprocessObserverThread(
        command=[
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr)",
        ],
        aggregation_queue=queue.Queue(),
        event_sink=[sink],
        notify_events=[],
        trace_id="trace-a",
        capture_output_events=True,
    )

    observer.run()
    events = drain(sink)

    started = [event for event in events if isinstance(event, ProcessStartedEvent)]
    exited = [event for event in events if isinstance(event, ProcessExitedEvent)]
    output = [event for event in events if isinstance(event, ProcessOutputEvent)]

    assert len(started) == 1
    assert started[0].pid > 0
    assert len(exited) == 1
    assert exited[0].return_code == 0
    assert exited[0].interrupted is False
    assert {(event.stream, event.line) for event in output} == {
        ("stdout", "out"),
        ("stderr", "err"),
    }


def test_subprocess_run_mode_passes_user_stdout_through(capsys):
    sink = queue.Queue()
    observer = SubprocessObserverThread(
        command=[sys.executable, "-c", "print('normal output')"],
        aggregation_queue=queue.Queue(),
        event_sink=[sink],
        notify_events=[],
        trace_id="trace-a",
        capture_output_events=False,
    )

    observer.run()
    events = drain(sink)

    assert "normal output" in capsys.readouterr().out
    assert not any(isinstance(event, ProcessOutputEvent) for event in events)
