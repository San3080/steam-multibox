from src.monitor import BoxState, WindowSnapshot, classify


def test_main_window_is_healthy_even_with_other_flags():
    snap = WindowSnapshot(main_window=True, account_picker=True)
    assert classify(snap, splash_timeout=40) == BoxState.HEALTHY


def test_retry_error_outranks_guard_prompt():
    snap = WindowSnapshot(retry_error=True, guard_prompt=True)
    assert classify(snap, splash_timeout=40) == BoxState.STUCK_RETRY


def test_guard_prompt_is_waiting_2fa():
    snap = WindowSnapshot(guard_prompt=True)
    assert classify(snap, splash_timeout=40) == BoxState.WAITING_2FA


def test_account_picker_detected():
    snap = WindowSnapshot(account_picker=True)
    assert classify(snap, splash_timeout=40) == BoxState.ACCOUNT_PICKER


def test_login_form_detected():
    snap = WindowSnapshot(login_form=True)
    assert classify(snap, splash_timeout=40) == BoxState.LOGIN_FORM


def test_splash_before_timeout_is_launching():
    snap = WindowSnapshot(splash_only=True, elapsed=10)
    assert classify(snap, splash_timeout=40) == BoxState.LAUNCHING


def test_splash_past_timeout_is_stuck_splash():
    snap = WindowSnapshot(splash_only=True, elapsed=41)
    assert classify(snap, splash_timeout=40) == BoxState.STUCK_SPLASH


def test_no_recognizable_window_is_unknown():
    assert classify(WindowSnapshot(), splash_timeout=40) == BoxState.UNKNOWN


def test_login_failed_is_recognised():
    snap = WindowSnapshot(login_failed=True)
    assert classify(snap, splash_timeout=40) == BoxState.LOGIN_FAILED


def test_main_window_outranks_login_failed():
    snap = WindowSnapshot(main_window=True, login_failed=True)
    assert classify(snap, splash_timeout=40) == BoxState.HEALTHY


def test_login_failed_outranks_login_form():
    snap = WindowSnapshot(login_form=True, login_failed=True)
    assert classify(snap, splash_timeout=40) == BoxState.LOGIN_FAILED
