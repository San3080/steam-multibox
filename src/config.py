"""Pemuatan, penyimpanan, dan validasi config.json."""
from dataclasses import dataclass, asdict, fields
import json
import os


@dataclass
class AppConfig:
    sandboxie_dir: str = ""
    steam_exe: str = ""
    accounts_file: str = "data/accounts.txt"
    box_prefix: str = "Steam_"
    stagger_seconds: int = 8
    login_method: str = "cmdline"
    auto_terminate_on_success: bool = False
    max_retries: int = 3
    retry_check_delay: int = 25
    poll_interval: int = 5
    splash_timeout: int = 40
    terminate_grace_seconds: int = 12
    # Discord webhook (opsional). Kosong = tidak ada notifikasi.
    discord_webhook_url: str = ""


def load_config(path: str) -> AppConfig:
    """Muat config dari JSON. File hilang -> nilai default. Field tak dikenal diabaikan."""
    if not os.path.exists(path):
        return AppConfig()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    known = {f.name for f in fields(AppConfig)}
    return AppConfig(**{k: v for k, v in data.items() if k in known})


def save_config(cfg: AppConfig, path: str) -> None:
    """Simpan config ke JSON (indent 2, UTF-8)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2)


def validate_config(cfg: AppConfig) -> list[str]:
    """Kembalikan daftar pesan error. Kosong = valid."""
    errors: list[str] = []
    if cfg.login_method not in ("cmdline", "ui"):
        errors.append("login_method harus 'cmdline' atau 'ui'")
    if cfg.max_retries < 0:
        errors.append("max_retries tidak boleh negatif")
    if cfg.stagger_seconds < 0:
        errors.append("stagger_seconds tidak boleh negatif")
    if cfg.retry_check_delay < 0:
        errors.append("retry_check_delay tidak boleh negatif")
    if cfg.poll_interval <= 0:
        errors.append("poll_interval harus > 0")
    if cfg.splash_timeout < 0:
        errors.append("splash_timeout tidak boleh negatif")
    return errors
