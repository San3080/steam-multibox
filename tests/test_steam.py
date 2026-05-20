from src.steam import build_login_args


def test_build_login_args():
    assert build_login_args(r"D:\Steam\steam.exe", "user1", "pass1") == [
        r"D:\Steam\steam.exe", "-login", "user1", "pass1"]


def test_build_login_args_preserves_special_chars_in_password():
    args = build_login_args(r"D:\Steam\steam.exe", "user1", "p@ss w0rd")
    assert args[3] == "p@ss w0rd"
