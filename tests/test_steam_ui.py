from src.steam_ui import is_account_picker_title, is_login_form_title


def test_account_picker_title_recognised():
    assert is_account_picker_title("Steam") is True            # picker pakai judul "Steam"
    assert is_account_picker_title("Who's playing?") is True


def test_login_form_title_recognised():
    assert is_login_form_title("Sign in to Steam") is True


def test_unrelated_title_not_matched():
    assert is_account_picker_title("Notepad") is False
    assert is_login_form_title("Notepad") is False
