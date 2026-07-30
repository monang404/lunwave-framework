import datetime

from lunawave_framework.core.logging.log_reader import parse_line, stats, tail


def test_parse_line_standard():
    line = "[14:02:10] INFO: WebSocket connected (client_id=8f2a, total=2)"
    parsed = parse_line(line)
    assert parsed["time"] == "14:02:10"
    assert parsed["level"] == "INFO"
    assert parsed["event"] == "WebSocket connected"
    assert parsed["fields"] == {"client_id": "8f2a", "total": "2"}


def test_parse_line_no_fields():
    line = "[14:02:10] ERROR: Something bad happened"
    parsed = parse_line(line)
    assert parsed["time"] == "14:02:10"
    assert parsed["level"] == "ERROR"
    assert parsed["event"] == "Something bad happened"
    assert parsed["fields"] == {}


def test_parse_line_banner():
    line = "==== SESSION START pid=41210 ===="
    parsed = parse_line(line)
    assert parsed["time"] == ""
    assert parsed["level"] == "BANNER"
    assert parsed["event"] == line
    assert parsed["fields"] == {}


def test_tail_filters(monkeypatch):
    lines = [
        "[10:00:00] INFO: event1 (category=system)",
        "[10:00:01] DEBUG: event2 (category=network, req_id=123)",
        "[10:00:02] ERROR: event3 (category=system)",
        "==== SESSION START ====",
    ]
    monkeypatch.setattr("lunawave_framework.core.logging.log_reader._get_all_lines", lambda: lines)

    res = tail(limit=2)
    assert len(res) == 2
    assert res[0]["level"] == "ERROR"
    assert res[1]["level"] == "BANNER"

    res = tail(limit=10, category="system")
    assert len(res) == 2
    assert res[0]["level"] == "INFO"
    assert res[1]["level"] == "ERROR"

    res = tail(limit=10, level="DEBUG")
    assert len(res) == 1
    assert res[0]["event"] == "event2"

    res = tail(limit=10, query="req_id=123")
    assert len(res) == 1
    assert res[0]["level"] == "DEBUG"


def test_stats(monkeypatch):
    try:
        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    except AttributeError:
        now = datetime.datetime.utcnow()
    t1 = now - datetime.timedelta(minutes=10)
    t2 = now - datetime.timedelta(minutes=5)
    t3 = now - datetime.timedelta(hours=2)  # Outside 1 hour window

    lines = [
        f"[{t3.strftime('%H:%M:%S')}] INFO: event (category=system)",
        f"[{t1.strftime('%H:%M:%S')}] ERROR: event (category=network)",
        f"[{t2.strftime('%H:%M:%S')}] INFO: event (category=system)",
        "==== SESSION START ====",
    ]
    monkeypatch.setattr("lunawave_framework.core.logging.log_reader._get_all_lines", lambda: lines)

    res = stats(window_seconds=3600)
    assert res["levels"]["INFO"] == 1
    assert res["levels"]["ERROR"] == 1
    assert res["categories"]["network"] == 1
    assert res["categories"]["system"] == 1
    assert "BANNER" not in res["levels"]
