from src.login_verify import (parse_account_names, parse_active_account,
                               verify_login)


def _write_vdf(tmp_path, content):
    """Helper: tulis loginusers.vdf di tata letak box dan kembalikan root box."""
    box_root = tmp_path / "box"
    cfg = box_root / "drive" / "C" / "Program Files (x86)" / "Steam" / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "loginusers.vdf").write_text(content, encoding="utf-8")
    return box_root


def test_parse_active_account_picks_most_recent():
    vdf = '''
    "users" {
        "76561198000000001" {
            "AccountName" "alice"
            "MostRecent" "0"
        }
        "76561198000000002" {
            "AccountName" "bob"
            "MostRecent" "1"
        }
    }
    '''
    assert parse_active_account(vdf) == "bob"


def test_parse_active_account_none_when_no_recent():
    vdf = '"AccountName" "alice"\n"MostRecent" "0"'
    assert parse_active_account(vdf) is None


def test_verify_login_uses_most_recent_when_multiple_accounts(tmp_path, monkeypatch):
    """vdf punya 'alice' DAN 'bob'; MostRecent=bob; expected=alice -> mismatch."""
    vdf = '''
    "users" {
        "76561198000000001" { "AccountName" "alice" "MostRecent" "0" }
        "76561198000000002" { "AccountName" "bob"   "MostRecent" "1" }
    }
    '''
    box_root = _write_vdf(tmp_path, vdf)
    monkeypatch.setattr("src.login_verify.find_box_root",
                        lambda box: str(box_root))
    ok, msg = verify_login("Steam_alice", "alice")
    assert ok is False
    assert "bob" in msg.lower()


def test_verify_login_match_when_most_recent_matches(tmp_path, monkeypatch):
    vdf = '''
    "users" {
        "76561198000000001" { "AccountName" "alice" "MostRecent" "1" }
        "76561198000000002" { "AccountName" "bob"   "MostRecent" "0" }
    }
    '''
    box_root = _write_vdf(tmp_path, vdf)
    monkeypatch.setattr("src.login_verify.find_box_root",
                        lambda box: str(box_root))
    ok, msg = verify_login("Steam_alice", "alice")
    assert ok is True
    assert "MostRecent" in msg


def test_parse_account_names_basic():
    vdf = '''
    "users"
    {
        "76561198000000000"
        {
            "AccountName"\t\t"testuser1"
            "PersonaName"\t\t"uaqikurydakazu"
        }
    }
    '''
    assert parse_account_names(vdf) == ["testuser1"]


def test_parse_account_names_multiple():
    vdf = '''
    "AccountName" "foo"
    "AccountName"   "bar"
    '''
    assert parse_account_names(vdf) == ["foo", "bar"]


def test_parse_account_names_none():
    assert parse_account_names("") == []


def test_verify_login_matches_case_insensitive(tmp_path, monkeypatch):
    box_root = tmp_path / "Sandbox" / "MyUser" / "Steam_alice"
    vdf_dir = box_root / "drive" / "C" / "Program Files (x86)" / "Steam" / "config"
    vdf_dir.mkdir(parents=True)
    (vdf_dir / "loginusers.vdf").write_text('"AccountName" "Alice"', encoding="utf-8")

    monkeypatch.setenv("USERNAME", "MyUser")
    monkeypatch.setattr("src.login_verify.find_box_root",
                        lambda box: str(box_root))
    ok, msg = verify_login("Steam_alice", "alice")
    assert ok is True
    assert "alice" in msg.lower()


def test_verify_login_mismatch(tmp_path, monkeypatch):
    box_root = tmp_path / "box"
    vdf_dir = box_root / "drive" / "C" / "Program Files (x86)" / "Steam" / "config"
    vdf_dir.mkdir(parents=True)
    (vdf_dir / "loginusers.vdf").write_text('"AccountName" "wrong_account"', encoding="utf-8")
    monkeypatch.setattr("src.login_verify.find_box_root",
                        lambda box: str(box_root))
    ok, msg = verify_login("Steam_alice", "alice")
    assert ok is False
    assert "wrong_account" in msg


def test_verify_login_no_vdf(tmp_path, monkeypatch):
    monkeypatch.setattr("src.login_verify.find_box_root",
                        lambda box: str(tmp_path))
    ok, msg = verify_login("Steam_alice", "alice")
    assert ok is None
    assert "loginusers.vdf" in msg


def test_verify_login_no_box_root(monkeypatch):
    monkeypatch.setattr("src.login_verify.find_box_root", lambda box: None)
    ok, msg = verify_login("Steam_alice", "alice")
    assert ok is None
    assert "tidak ditemukan" in msg


def test_wipe_steam_session_removes_known_files(tmp_path):
    from src.login_verify import wipe_steam_session
    box_root = tmp_path
    config = box_root / "drive" / "C" / "Program Files (x86)" / "Steam" / "config"
    steam = config.parent
    config.mkdir(parents=True)
    (config / "loginusers.vdf").write_text("x")
    (config / "config.vdf").write_text("x")
    (steam / "ssfn1234567890").write_text("x")
    (steam / "ssfn0987654321").write_text("x")
    (steam / "unrelated.txt").write_text("x")

    n, removed = wipe_steam_session(str(box_root))
    assert n == 4
    assert not (config / "loginusers.vdf").exists()
    assert not (config / "config.vdf").exists()
    assert len(list(steam.glob("ssfn*"))) == 0
    # file lain TIDAK boleh ikut hapus
    assert (steam / "unrelated.txt").exists()


def test_wipe_steam_session_nonexistent_root(tmp_path):
    from src.login_verify import wipe_steam_session
    n, removed = wipe_steam_session(str(tmp_path / "missing"))
    assert n == 0
    assert removed == []


def test_wipe_steam_session_empty_dir(tmp_path):
    from src.login_verify import wipe_steam_session
    n, removed = wipe_steam_session(str(tmp_path))
    assert n == 0
    assert removed == []


def test_enable_remember_password_flips_zero_to_one(tmp_path):
    from src.login_verify import enable_remember_password
    box_root = tmp_path
    config = box_root / "drive" / "C" / "Program Files (x86)" / "Steam" / "config"
    config.mkdir(parents=True)
    vdf = config / "loginusers.vdf"
    vdf.write_text(
        '"users"\n{\n'
        '\t"76561198000000000"\n\t{\n'
        '\t\t"AccountName"\t\t"testuser1"\n'
        '\t\t"RememberPassword"\t"0"\n'
        '\t}\n}\n',
        encoding="utf-8")
    assert enable_remember_password(str(box_root)) is True
    assert '"RememberPassword"\t"1"' in vdf.read_text(encoding="utf-8")


def test_enable_remember_password_idempotent_when_already_one(tmp_path):
    from src.login_verify import enable_remember_password
    box_root = tmp_path
    config = box_root / "drive" / "C" / "Program Files (x86)" / "Steam" / "config"
    config.mkdir(parents=True)
    (config / "loginusers.vdf").write_text(
        '"RememberPassword"\t"1"\n', encoding="utf-8")
    # tidak ada "0" untuk diubah -> return False, file tidak ditulis ulang
    assert enable_remember_password(str(box_root)) is False


def test_enable_remember_password_no_vdf(tmp_path):
    from src.login_verify import enable_remember_password
    assert enable_remember_password(str(tmp_path / "missing")) is False


def test_enable_remember_password_no_box_root():
    from src.login_verify import enable_remember_password
    assert enable_remember_password("") is False
