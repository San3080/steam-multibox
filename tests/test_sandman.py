from unittest.mock import patch
from src import sandman


def test_find_sandman_for_plus(tmp_path):
    (tmp_path / "SandMan.exe").write_bytes(b"")
    assert sandman.find_sandboxie_ui(str(tmp_path)) == str(tmp_path / "SandMan.exe")


def test_find_sbiectrl_for_classic(tmp_path):
    (tmp_path / "SbieCtrl.exe").write_bytes(b"")
    assert sandman.find_sandboxie_ui(str(tmp_path)) == str(tmp_path / "SbieCtrl.exe")


def test_find_prefers_sandman_when_both_exist(tmp_path):
    (tmp_path / "SandMan.exe").write_bytes(b"")
    (tmp_path / "SbieCtrl.exe").write_bytes(b"")
    assert sandman.find_sandboxie_ui(str(tmp_path)).endswith("SandMan.exe")


def test_find_returns_none_when_missing(tmp_path):
    assert sandman.find_sandboxie_ui(str(tmp_path)) is None


def test_find_returns_none_for_empty_dir():
    assert sandman.find_sandboxie_ui("") is None


def test_open_sandboxie_ui_success(tmp_path):
    (tmp_path / "SandMan.exe").write_bytes(b"")
    with patch.object(sandman.subprocess, "Popen") as popen:
        ok, msg = sandman.open_sandboxie_ui(str(tmp_path))
    assert ok is True
    popen.assert_called_once()


def test_open_sandboxie_ui_when_missing(tmp_path):
    ok, msg = sandman.open_sandboxie_ui(str(tmp_path))
    assert ok is False
    assert "tidak ditemukan" in msg
