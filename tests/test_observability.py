from __future__ import annotations

import re

import wbsb.observability.logging as logging_mod


def test_pseudonymize_ipv4() -> None:
    assert logging_mod.pseudonymize_ip("192.168.1.47") == "192.168.1.0"


def test_pseudonymize_ipv4_last_zero() -> None:
    assert logging_mod.pseudonymize_ip("10.0.0.1") == "10.0.0.0"


def test_pseudonymize_ipv6() -> None:
    assert (
        logging_mod.pseudonymize_ip("2001:db8:0:0:0:0:0:1")
        == "2001:db8:0:0:0:0:0:0"
    )


def test_pseudonymize_invalid_input() -> None:
    assert logging_mod.pseudonymize_ip("not-an-ip") == "not-an-ip"


def test_log_security_event_emits(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeLogger:
        def info(self, event: str, **kwargs: object) -> None:
            captured["event"] = event
            captured["fields"] = kwargs

    monkeypatch.setattr(logging_mod, "get_logger", lambda: FakeLogger())

    result = logging_mod.log_security_event(
        logging_mod.EVENT_AUTH_FAILURE,
        source_ip="1.2.3.0",
        reason="test",
    )

    assert result is None
    assert captured["event"] == logging_mod.EVENT_AUTH_FAILURE
    assert captured["fields"] == {
        "source_ip": "1.2.3.0",
        "reason": "test",
        "timestamp": captured["fields"]["timestamp"],
    }


def test_log_security_event_has_timestamp(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeLogger:
        def info(self, event: str, **kwargs: object) -> None:
            captured["event"] = event
            captured["fields"] = kwargs

    monkeypatch.setattr(logging_mod, "get_logger", lambda: FakeLogger())

    logging_mod.log_security_event(
        logging_mod.EVENT_AUTH_FAILURE,
        source_ip="1.2.3.0",
        reason="test",
    )

    timestamp = captured["fields"]["timestamp"]
    assert isinstance(timestamp, str)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", timestamp)
