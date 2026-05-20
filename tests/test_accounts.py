from src.accounts import Account, read_accounts, write_failures


def test_read_valid_accounts(tmp_path):
    p = tmp_path / "accounts.txt"
    p.write_text("user1,pass1\nuser2,pass2\n", encoding="utf-8")
    accounts, errors = read_accounts(str(p))
    assert errors == []
    assert accounts == [Account("user1", "pass1", 1), Account("user2", "pass2", 2)]


def test_read_skips_blank_and_comment_lines(tmp_path):
    p = tmp_path / "accounts.txt"
    p.write_text("# komentar\n\nuser1,pass1\n", encoding="utf-8")
    accounts, errors = read_accounts(str(p))
    assert errors == []
    assert accounts == [Account("user1", "pass1", 3)]


def test_read_reports_malformed_line_with_number(tmp_path):
    p = tmp_path / "accounts.txt"
    p.write_text("user1,pass1\nbroken_line_no_separator\n", encoding="utf-8")
    accounts, errors = read_accounts(str(p))
    assert len(accounts) == 1
    assert len(errors) == 1
    assert "Baris 2" in errors[0]


def test_read_supports_pipe_separator(tmp_path):
    """Pipe '|' juga diterima sebagai pemisah selain koma."""
    p = tmp_path / "accounts.txt"
    p.write_text("user1|pass1\nuser2|pass2\n", encoding="utf-8")
    accounts, errors = read_accounts(str(p))
    assert errors == []
    assert accounts == [Account("user1", "pass1", 1), Account("user2", "pass2", 2)]


def test_read_mixes_pipe_and_comma_per_line(tmp_path):
    """Tiap baris boleh pakai pemisah yang berbeda."""
    p = tmp_path / "accounts.txt"
    p.write_text("user1,pass1\nuser2|pass2\n", encoding="utf-8")
    accounts, errors = read_accounts(str(p))
    assert errors == []
    assert [a.username for a in accounts] == ["user1", "user2"]
    assert [a.password for a in accounts] == ["pass1", "pass2"]


def test_read_uses_earliest_separator(tmp_path):
    """Kalau ada baik koma maupun pipe, yang muncul duluan jadi pemisah."""
    p = tmp_path / "accounts.txt"
    # pipe duluan -> user1 | "pass,1"
    p.write_text("user1|pass,1\n", encoding="utf-8")
    accounts, _ = read_accounts(str(p))
    assert accounts == [Account("user1", "pass,1", 1)]


def test_read_reports_empty_username_or_password(tmp_path):
    p = tmp_path / "accounts.txt"
    p.write_text("user1,\n,pass2\n", encoding="utf-8")
    accounts, errors = read_accounts(str(p))
    assert accounts == []
    assert len(errors) == 2


def test_read_missing_file_returns_error(tmp_path):
    accounts, errors = read_accounts(str(tmp_path / "nope.txt"))
    assert accounts == []
    assert len(errors) == 1


def test_write_failures_format(tmp_path):
    p = tmp_path / "fail.txt"
    write_failures(str(p), [
        (Account("user1", "pass1", 1), "stuck splash 3x"),
        (Account("user2", "pass2", 2), "box gagal dibuat"),
    ])
    content = p.read_text(encoding="utf-8")
    assert content == (
        "user1,pass1  # stuck splash 3x\n"
        "user2,pass2  # box gagal dibuat\n"
    )


def test_write_failures_empty_list_writes_empty_file(tmp_path):
    p = tmp_path / "fail.txt"
    write_failures(str(p), [])
    assert p.read_text(encoding="utf-8") == ""


def test_write_failures_creates_parent_directory(tmp_path):
    """Folder induk dibuat otomatis kalau belum ada (mis. folder `data/` baru)."""
    p = tmp_path / "data" / "fail.txt"
    assert not p.parent.exists()
    write_failures(str(p), [(Account("u1", "p1", 1), "alasan")])
    assert p.read_text(encoding="utf-8") == "u1,p1  # alasan\n"


def test_update_credential_replaces_only_matching_line(tmp_path):
    from src.accounts import update_credential
    p = tmp_path / "accounts.txt"
    p.write_text("# komentar\nu1,p1\nu2,p2\nu3|p3\n", encoding="utf-8")
    assert update_credential(str(p), "u2", "newuser", "newpass") is True
    assert p.read_text(encoding="utf-8") == "# komentar\nu1,p1\nnewuser,newpass\nu3|p3\n"


def test_update_credential_case_insensitive_match(tmp_path):
    from src.accounts import update_credential
    p = tmp_path / "accounts.txt"
    p.write_text("Alice,oldpw\n", encoding="utf-8")
    assert update_credential(str(p), "alice", "alice", "newpw") is True
    assert p.read_text(encoding="utf-8") == "alice,newpw\n"


def test_update_credential_no_match_returns_false(tmp_path):
    from src.accounts import update_credential
    p = tmp_path / "accounts.txt"
    p.write_text("u1,p1\n", encoding="utf-8")
    assert update_credential(str(p), "nobody", "x", "y") is False
    assert p.read_text(encoding="utf-8") == "u1,p1\n"


def test_update_credential_missing_file_returns_false(tmp_path):
    from src.accounts import update_credential
    assert update_credential(str(tmp_path / "nope.txt"), "u", "x", "y") is False


def test_update_credential_preserves_pipe_separated_other_lines(tmp_path):
    from src.accounts import update_credential
    p = tmp_path / "accounts.txt"
    p.write_text("u1|p1\nu2,p2\n", encoding="utf-8")
    update_credential(str(p), "u1", "u1", "newp1")
    # baris u1 dikonversi ke koma, baris u2 tetap sebagaimana adanya
    assert p.read_text(encoding="utf-8") == "u1,newp1\nu2,p2\n"
