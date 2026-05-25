import logging

class EventSinkHandler(logging.Handler):
    """Forwards log records into the TrackerEvent stream."""
    def __init__(self, event_sink: List[Queue[TrackerEvent]]):
        super().__init__()
        self.event_sink = event_sink

    def emit(self, record: logging.LogRecord):
        event = DiagnosticEvent(
            severity=record.levelname,
            message=self.format(record),
            source=record.name,
            timestamp=datetime.fromtimestamp(record.created),
        )
        for sink in self.event_sink:
            sink.put(event)