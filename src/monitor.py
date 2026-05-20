"""Klasifikasi keadaan box Steam dari snapshot jendela yang terdeteksi."""
from dataclasses import dataclass
from enum import Enum


class BoxState(Enum):
    LAUNCHING = "Launching"
    HEALTHY = "Healthy"
    ACCOUNT_PICKER = "Pemilih akun"
    LOGIN_FORM = "Form login"
    WAITING_2FA = "Tunggu 2FA"
    LOGIN_FAILED = "Login gagal (password salah)"
    STUCK_RETRY = "Stuck retry"
    STUCK_SPLASH = "Stuck splash"
    UNKNOWN = "Ragu"


@dataclass
class WindowSnapshot:
    """Ringkasan jendela Steam yang terdeteksi di sebuah box pada satu saat."""
    main_window: bool = False
    account_picker: bool = False
    login_form: bool = False
    guard_prompt: bool = False
    retry_error: bool = False
    login_failed: bool = False
    splash_only: bool = False
    elapsed: float = 0.0      # detik sejak launch


def classify(snap: WindowSnapshot, splash_timeout: float) -> BoxState:
    """Tentukan keadaan box. Urutan prioritas penting:

    main_window menang mutlak (sudah login). retry_error diperiksa sebelum
    guard_prompt agar box error tidak salah dikira menunggu 2FA.
    """
    if snap.main_window:
        return BoxState.HEALTHY
    if snap.retry_error:
        return BoxState.STUCK_RETRY
    if snap.login_failed:
        return BoxState.LOGIN_FAILED
    if snap.guard_prompt:
        return BoxState.WAITING_2FA
    if snap.account_picker:
        return BoxState.ACCOUNT_PICKER
    if snap.login_form:
        return BoxState.LOGIN_FORM
    if snap.splash_only:
        if snap.elapsed >= splash_timeout:
            return BoxState.STUCK_SPLASH
        return BoxState.LAUNCHING
    return BoxState.UNKNOWN
