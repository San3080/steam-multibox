from unittest.mock import patch
import subprocess
from src import host_steam


def test_is_host_steam_running_true_when_in_output():
    fake = "steam.exe        1234 Console        1     50,000 K\n"
    with patch.object(subprocess, "check_output", return_value=fake):
        assert host_steam.is_host_steam_running() is True


def test_is_host_steam_running_false_when_absent():
    with patch.object(subprocess, "check_output", return_value="INFO: No tasks running.\n"):
        assert host_steam.is_host_steam_running() is False


def test_is_host_steam_running_false_on_error():
    with patch.object(subprocess, "check_output",
                      side_effect=FileNotFoundError):
        assert host_steam.is_host_steam_running() is False


def test_kill_host_steam_success(monkeypatch):
    class R:
        returncode = 0
        stdout = "SUCCESS: ..."
        stderr = ""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: R())
    ok, msg = host_steam.kill_host_steam()
    assert ok is True
    assert "Steam" in msg


def test_kill_host_steam_no_process(monkeypatch):
    class R:
        returncode = 128
        stdout = ""
        stderr = "ERROR: The process \"steam.exe\" not found."
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: R())
    ok, msg = host_steam.kill_host_steam()
    assert ok is True
    assert "Tidak ada" in msg or "not" in msg.lower()


def test_kill_host_steam_failure(monkeypatch):
    class R:
        returncode = 1
        stdout = ""
        stderr = "access denied"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: R())
    ok, msg = host_steam.kill_host_steam()
    assert ok is False
