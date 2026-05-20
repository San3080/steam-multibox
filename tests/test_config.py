import json
from src.config import AppConfig, load_config, save_config, validate_config


def test_load_missing_file_returns_defaults(tmp_path):
    cfg = load_config(str(tmp_path / "nope.json"))
    assert cfg == AppConfig()
    assert cfg.box_prefix == "Steam_"
    assert cfg.auto_terminate_on_success is False


def test_load_reads_known_fields_and_ignores_unknown(tmp_path):
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"box_prefix": "S_", "max_retries": 5, "bogus": 1}))
    cfg = load_config(str(p))
    assert cfg.box_prefix == "S_"
    assert cfg.max_retries == 5


def test_save_then_load_roundtrip(tmp_path):
    p = str(tmp_path / "config.json")
    original = AppConfig(steam_exe="C:\\Steam\\steam.exe", auto_terminate_on_success=True)
    save_config(original, p)
    assert load_config(p) == original


def test_validate_flags_bad_login_method():
    errors = validate_config(AppConfig(login_method="weird"))
    assert any("login_method" in e for e in errors)


def test_validate_flags_negative_numbers():
    errors = validate_config(AppConfig(max_retries=-1, stagger_seconds=-3))
    assert len(errors) == 2


def test_validate_ok_config_has_no_errors():
    assert validate_config(AppConfig()) == []


def test_validate_flags_non_positive_poll_interval():
    errors = validate_config(AppConfig(poll_interval=0))
    assert any("poll_interval" in e for e in errors)
