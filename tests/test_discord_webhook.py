"""Tes pure-logic Discord webhook helpers. Tidak ada koneksi nyata —
semua HTTP di-mock."""
import json
from unittest.mock import patch, MagicMock

from src import discord_webhook as dw


def _mock_urlopen_ok():
    """Context manager mock untuk urlopen status 204 (Discord default)."""
    fake_resp = MagicMock()
    fake_resp.status = 204
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)
    return fake_resp


def test_send_message_returns_true_on_2xx():
    with patch.object(dw.urllib.request, "urlopen",
                      return_value=_mock_urlopen_ok()):
        assert dw.send_message("https://discord.com/api/webhooks/x/y",
                               "halo") is True


def test_send_message_returns_false_on_empty_url():
    assert dw.send_message("", "halo") is False
    assert dw.send_message("   ", "halo") is False


def test_send_message_returns_false_on_network_error():
    with patch.object(dw.urllib.request, "urlopen",
                      side_effect=OSError("no net")):
        assert dw.send_message("https://x", "halo") is False


def test_send_message_truncates_long_content():
    captured = {}
    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _mock_urlopen_ok()
    long_msg = "x" * 5000
    with patch.object(dw.urllib.request, "urlopen", side_effect=fake_urlopen):
        dw.send_message("https://x", long_msg)
    assert len(captured["body"]["content"]) <= 1900


def test_notify_run_start_format():
    with patch.object(dw, "send_message", return_value=True) as send:
        dw.notify_run_start("https://x", "Run Semua", 6)
    args, _ = send.call_args
    assert "Run Semua" in args[1]
    assert "6 akun" in args[1]


def test_notify_run_done_with_failures_lists_them():
    with patch.object(dw, "send_message", return_value=True) as send:
        dw.notify_run_done("https://x", 1, 2,
                           failures=[("u2", "stuck"), ("u3", "password salah")])
    args, _ = send.call_args
    body = args[1]
    assert "1 sukses" in body and "2 gagal" in body
    assert "u2" in body and "stuck" in body
    assert "u3" in body and "password salah" in body


def test_notify_run_done_success_only_uses_check_icon():
    with patch.object(dw, "send_message", return_value=True) as send:
        dw.notify_run_done("https://x", 5, 0)
    args, _ = send.call_args
    assert "✅" in args[1]


def test_notify_login_success():
    with patch.object(dw, "send_message", return_value=True) as send:
        dw.notify_login("https://x", "alice", True)
    args, _ = send.call_args
    assert "alice" in args[1] and "berhasil" in args[1].lower()


def test_notify_login_failure_includes_detail():
    with patch.object(dw, "send_message", return_value=True) as send:
        dw.notify_login("https://x", "bob", False, "password salah")
    args, _ = send.call_args
    assert "bob" in args[1] and "password salah" in args[1]


def test_notify_edit_password_only():
    with patch.object(dw, "send_message", return_value=True) as send:
        dw.notify_edit("https://x", "alice", "alice", password_changed=True)
    args, _ = send.call_args
    assert "alice" in args[1] and "password" in args[1].lower()


def test_notify_edit_rename():
    with patch.object(dw, "send_message", return_value=True) as send:
        dw.notify_edit("https://x", "alice", "alice2", password_changed=True)
    args, _ = send.call_args
    assert "alice" in args[1] and "alice2" in args[1]
