from unittest.mock import patch, MagicMock
from src.sandboxie import Sandboxie


def make() -> Sandboxie:
    return Sandboxie(r"C:\Program Files\Sandboxie")


def test_create_box_cmd():
    sb = make()
    assert sb.create_box_cmd("Steam_user1") == [
        r"C:\Program Files\Sandboxie\SbieIni.exe", "set", "Steam_user1", "Enabled", "y"]


def test_delete_box_cmd():
    sb = make()
    assert sb.delete_box_cmd("Steam_user1") == [
        r"C:\Program Files\Sandboxie\SbieIni.exe", "delete", "Steam_user1"]


def test_launch_cmd_with_args():
    sb = make()
    assert sb.launch_cmd("Steam_user1", r"D:\Steam\steam.exe", ["-login", "u", "p"]) == [
        r"C:\Program Files\Sandboxie\Start.exe", "/box:Steam_user1",
        r"D:\Steam\steam.exe", "-login", "u", "p"]


def test_launch_cmd_without_args():
    sb = make()
    assert sb.launch_cmd("Steam_user1", r"D:\Steam\steam.exe") == [
        r"C:\Program Files\Sandboxie\Start.exe", "/box:Steam_user1",
        r"D:\Steam\steam.exe"]


def test_terminate_cmd():
    sb = make()
    assert sb.terminate_cmd("Steam_user1") == [
        r"C:\Program Files\Sandboxie\Start.exe", "/box:Steam_user1", "/terminate"]


def test_create_box_runs_create_cmd():
    sb = make()
    with patch("src.sandboxie.subprocess.run") as run:
        sb.create_box("Steam_user1")
    # First call is the enable command; later calls add HideMessage.
    assert run.call_args_list[0].args[0] == sb.create_box_cmd("Steam_user1")
    assert run.call_args_list[0].kwargs == {"check": True}


def test_set_setting_cmd():
    sb = make()
    with patch("src.sandboxie.subprocess.run") as run:
        sb.set_setting("Steam_user1", "BorderColor", "#FFCC00,ttl,6")
    run.assert_called_once_with(
        [sb.sbieini_exe, "set", "Steam_user1", "BorderColor", "#FFCC00,ttl,6"],
        check=True)


def test_append_setting_cmd():
    sb = make()
    with patch("src.sandboxie.subprocess.run") as run:
        sb.append_setting("Steam_user1", "HideMessage", "2206")
    run.assert_called_once_with(
        [sb.sbieini_exe, "append", "Steam_user1", "HideMessage", "2206"],
        check=True)


def test_create_box_also_silences_noisy_messages(monkeypatch):
    """create_box harus juga menambah HideMessage untuk pesan SBIE non-fatal."""
    sb = make()
    calls = []
    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        class R:
            returncode = 0
        return R()
    monkeypatch.setattr("src.sandboxie.subprocess.run", fake_run)
    sb.create_box("Steam_user1")
    # call 0: set Enabled y
    assert calls[0] == sb.create_box_cmd("Steam_user1")
    # call 1..N: append HideMessage <code>
    appended_codes = []
    for c in calls[1:]:
        assert c[1] == "append" and c[2] == "Steam_user1" and c[3] == "HideMessage"
        appended_codes.append(c[4])
    assert "2206" in appended_codes
    assert "2326" in appended_codes


def test_launch_uses_popen():
    sb = make()
    with patch("src.sandboxie.subprocess.Popen", return_value=MagicMock()) as popen:
        sb.launch("Steam_user1", r"D:\Steam\steam.exe", ["-login", "u", "p"])
    popen.assert_called_once_with(sb.launch_cmd(
        "Steam_user1", r"D:\Steam\steam.exe", ["-login", "u", "p"]))


def test_delete_box_runs_terminate_then_delete_sandbox_then_reload(monkeypatch, tmp_path):
    """delete_box: terminate -> delete_sandbox -> edit ini -> reload."""
    sb = make()
    ini = tmp_path / "Sandboxie.ini"
    ini.write_text(
        "[GlobalSettings]\nKey=val\n\n[Steam_user1]\nEnabled=y\n\n[Other]\nFoo=bar\n",
        encoding="utf-8")
    monkeypatch.setattr(sb, "_find_sandboxie_ini", lambda: str(ini))

    calls = []
    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()
    monkeypatch.setattr("src.sandboxie.subprocess.run", fake_run)

    sb.delete_box("Steam_user1")

    # Pengamatan urutan eksekusi
    assert calls[0] == sb.terminate_cmd("Steam_user1")
    assert calls[1][:3] == [sb.start_exe, "/box:Steam_user1", "delete_sandbox"]
    assert calls[2] == [sb.sbieini_exe, "reload"]

    # Section [Steam_user1] hilang, section lain tetap
    content = ini.read_text(encoding="utf-8")
    assert "[Steam_user1]" not in content
    assert "[GlobalSettings]" in content
    assert "[Other]" in content


def test_delete_box_raises_when_ini_not_found(monkeypatch):
    sb = make()
    monkeypatch.setattr(sb, "_find_sandboxie_ini", lambda: None)
    monkeypatch.setattr("src.sandboxie.subprocess.run",
                        lambda *a, **k: type("R", (), {"returncode": 0,
                                                       "stdout": "", "stderr": ""})())
    try:
        sb.delete_box("Steam_user1")
        assert False, "should have raised"
    except RuntimeError as e:
        assert "Sandboxie.ini" in str(e)


def test_delete_box_raises_when_section_missing(monkeypatch, tmp_path):
    sb = make()
    ini = tmp_path / "Sandboxie.ini"
    ini.write_text("[GlobalSettings]\nKey=val\n", encoding="utf-8")
    monkeypatch.setattr(sb, "_find_sandboxie_ini", lambda: str(ini))
    monkeypatch.setattr("src.sandboxie.subprocess.run",
                        lambda *a, **k: type("R", (), {"returncode": 0,
                                                       "stdout": "", "stderr": ""})())
    try:
        sb.delete_box("Steam_user1")
        assert False, "should have raised"
    except RuntimeError as e:
        assert "tidak ditemukan" in str(e).lower() or "section" in str(e).lower()


def test_remove_box_section_preserves_other_sections(tmp_path):
    """Helper unit-test: section di luar target tidak ikut terhapus."""
    sb = make()
    ini = tmp_path / "Sandboxie.ini"
    ini.write_text(
        "[GlobalSettings]\nA=1\n\n[Steam_alpha]\nEnabled=y\nFile=x\n\n[Steam_beta]\nEnabled=y\n",
        encoding="utf-8")
    ok = sb._remove_box_section_from_ini(str(ini), "Steam_alpha")
    assert ok is True
    text = ini.read_text(encoding="utf-8")
    assert "[Steam_alpha]" not in text
    assert "Enabled=y\nFile=x" not in text
    assert "[Steam_beta]" in text
    assert "[GlobalSettings]" in text


def test_remove_box_section_utf16(tmp_path):
    """Sandboxie.ini biasanya UTF-16 LE BOM; helper harus tetap bisa."""
    sb = make()
    ini = tmp_path / "Sandboxie.ini"
    content = "[GlobalSettings]\r\nA=1\r\n\r\n[Steam_x]\r\nEnabled=y\r\n"
    ini.write_bytes(b"\xff\xfe" + content.encode("utf-16-le"))
    ok = sb._remove_box_section_from_ini(str(ini), "Steam_x")
    assert ok is True
    text = ini.read_bytes()
    # Tetap UTF-16 setelah ditulis ulang
    assert text.startswith(b"\xff\xfe") or text[:2] in (b"\xff\xfe", b"\xfe\xff")


def test_silence_global_appends_to_globalsettings(monkeypatch):
    sb = make()
    calls = []
    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        class R:
            returncode = 0
        return R()
    monkeypatch.setattr("src.sandboxie.subprocess.run", fake_run)
    sb.silence_global_noisy_messages()
    # tiap call adalah append HideMessage <code> ke [GlobalSettings]
    for c in calls:
        assert c[1] == "append"
        assert c[2] == "GlobalSettings"
        assert c[3] == "HideMessage"
    # minimal beberapa code populer harus masuk
    appended = {c[4] for c in calls}
    assert "2206" in appended
    assert "2326" in appended
    assert "2191" in appended


def test_set_global_uses_globalsettings_section(monkeypatch):
    sb = make()
    with patch("src.sandboxie.subprocess.run") as run:
        sb.set_global("FileRootPath", r"D:\Sandbox\%USER%\%SANDBOX%")
    run.assert_called_once_with(
        [sb.sbieini_exe, "set", "GlobalSettings", "FileRootPath",
         r"D:\Sandbox\%USER%\%SANDBOX%"],
        check=True)


