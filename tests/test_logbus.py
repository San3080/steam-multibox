from src.logbus import LogBus, LogEntry


def test_log_entry_format_with_username():
    entry = LogEntry("01:19:27", "info", "user1", "launching")
    assert entry.format() == "01:19:27  user1  launching"


def test_log_entry_format_without_username():
    entry = LogEntry("01:19:27", "info", "", "aplikasi mulai")
    assert entry.format() == "01:19:27  aplikasi mulai"


def test_log_appends_entry_and_returns_it():
    bus = LogBus()
    entry = bus.log("halo", username="user1", level="ok")
    assert entry.message == "halo"
    assert entry.level == "ok"
    assert bus.all_entries() == [entry]


def test_all_text_joins_formatted_entries():
    bus = LogBus()
    bus.log("baris satu", username="u1")
    bus.log("baris dua", username="u2")
    text = bus.all_text()
    assert "u1  baris satu" in text
    assert "u2  baris dua" in text
    assert text.count("\n") == 1


def test_listener_called_on_log():
    bus = LogBus()
    received = []
    bus.add_listener(received.append)
    entry = bus.log("ping")
    assert received == [entry]
