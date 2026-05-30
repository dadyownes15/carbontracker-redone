import json
import queue
from datetime import datetime

from carbontracker.core.event_codec import (
    event_from_json,
    event_to_dict,
    event_to_json,
    events_from_jsonl_lines,
)
from carbontracker.core.events import (
    DiagnosticEvent,
    FinishedSession,
    LogSeverity,
    MeasurementEvent,
    ProcessOutputEvent,
    ProcessStartedEvent,
    SessionMetadata,
    StartedSession,
)
from carbontracker.core.profiling import PowerDomain, PowerSample
from carbontracker.core.stats import SessionFinalStats
from carbontracker.providers.power.power_provider import PowerMeasurementData
from carbontracker.reporters.file_logger import FileWriterThread


def metadata() -> SessionMetadata:
    return SessionMetadata(
        project_name="project-a",
        run_name="run-a",
        log_dir="logs",
        log_file_path="logs/run-a_events.jsonl",
        command=("python", "train.py"),
        trace_id="trace-a",
        config_summary={"components": ["cpu"], "pue": 1.1},
    )


def test_event_json_starts_with_type_and_identity_fields():
    event = StartedSession(timestamp=datetime(2026, 1, 1, 12), metadata=metadata())

    encoded = event_to_json(event)
    keys = list(json.loads(encoded).keys())

    assert keys[:4] == ["__type__", "timestamp", "project_name", "run_name"]


def test_round_trips_session_process_measurement_and_finished_events():
    timestamp = datetime(2026, 1, 1, 12)
    power_sample = PowerSample(
        observed_at=timestamp,
        domain=PowerDomain.CPU,
        device_id="cpu:0",
        source="test",
        watts=42.0,
    )
    events = [
        StartedSession(timestamp=timestamp, metadata=metadata()),
        ProcessStartedEvent(
            timestamp=timestamp,
            command=("python", "train.py"),
            pid=1234,
            trace_id="trace-a",
        ),
        MeasurementEvent(
            provider_name="power",
            timestamp=timestamp,
            data=PowerMeasurementData(timestamp=timestamp, samples=(power_sample,)),
        ),
        FinishedSession(
            timestamp=timestamp,
            metadata=metadata(),
            stats=SessionFinalStats(
                total_emissions_g=1.0,
                total_power_usage_kwh=2.0,
                duration_s=3.0,
                completed_spans_count=4,
            ),
        ),
    ]

    for event in events:
        decoded = event_from_json(event_to_json(event))
        assert decoded == event


def test_replay_fixture_decodes_supported_events():
    with open("test/fixtures/replay_session_events.jsonl") as handle:
        decoded = list(events_from_jsonl_lines(handle))

    assert [type(event).__name__ for event in decoded] == [
        "StartedSession",
        "ProcessStartedEvent",
        "ProcessExitedEvent",
    ]


def test_malformed_jsonl_lines_become_diagnostic_events():
    decoded = list(events_from_jsonl_lines(["not-json\n", '{"ok": true}\n']))

    assert all(isinstance(event, DiagnosticEvent) for event in decoded)
    assert decoded[0].severity == LogSeverity.WARNING
    assert "line 1" in decoded[0].message


def test_file_writer_skips_process_output_by_default(tmp_path):
    event_queue = queue.Queue()
    writer = FileWriterThread(
        log_dir=str(tmp_path),
        run_name="run-a",
        event_queue=event_queue,
    )
    writer.start()
    event_queue.put(
        ProcessOutputEvent(
            timestamp=datetime(2026, 1, 1, 12),
            stream="stdout",
            line="user output",
            trace_id="trace-a",
        )
    )
    event_queue.put(
        DiagnosticEvent(
            timestamp=datetime(2026, 1, 1, 12),
            severity=LogSeverity.WARNING,
            message="warning",
            logger_name="test",
        )
    )
    writer.stop()
    writer.join()

    lines = writer.log_file_path.read_text().splitlines()
    assert len(lines) == 1
    assert event_to_dict(event_from_json(lines[0]))["__type__"] == "DiagnosticEvent"
