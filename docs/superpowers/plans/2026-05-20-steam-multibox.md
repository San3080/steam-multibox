# Steam Multi-Box Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows GUI desktop app (Python + CustomTkinter) that auto-creates Sandboxie profiles, runs Steam in each with auto-login (turn-based), monitors for stuck states, and records failures to `fail.txt`.

**Architecture:** Pure-logic core modules (config, accounts, detect, logbus, command builders, window-state classifier) are TDD-tested. IO layers (Sandboxie subprocess, Steam window automation via pywinauto) are thin wrappers. A `Controller` orchestrates a turn-based run on a background thread and pushes updates to the GUI through a thread-safe queue. The GUI (Layout A: sidebar with actions + log panel, right-side box list) is built with CustomTkinter and tested manually.

**Tech Stack:** Python 3.10+, CustomTkinter (GUI), pywinauto (window automation), pytest (tests), Sandboxie CLI (`Start.exe`, `SbieIni.exe`), `steam.exe -login`.

**Spec:** `docs/superpowers/specs/2026-05-20-steam-multibox-design.md`

---

## Conventions

- Run all commands from the project root: `D:\project tools\auto create profile sandboxie`.
- Run tests with: `python -m pytest -v`
- Source code lives in `src/`; tests import as `from src.<module> import ...`.
- Commit after every task with the message shown in the task's commit step.
- Windows-only modules (`detect.py` uses `winreg`) are still importable and testable on Windows.

---

## Task 1: Project scaffold

**Files:**
- Create: `.gitignore`, `requirements.txt`, `pyproject.toml`, `README.md`
- Create: `config.example.json`, `accounts.example.txt`
- Create: `src/__init__.py`, `src/ui/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/

# runtime files — contain plaintext passwords, never commit
config.json
accounts.txt
fail.txt
```

- [ ] **Step 2: Create `requirements.txt`**

```text
customtkinter>=5.2.0
pywinauto>=0.6.8
pytest>=8.0.0
```

- [ ] **Step 3: Create `pyproject.toml`** (makes `src` importable in tests)

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 4: Create `config.example.json`**

```json
{
  "sandboxie_dir": "",
  "steam_exe": "",
  "accounts_file": "accounts.txt",
  "box_prefix": "Steam_",
  "stagger_seconds": 8,
  "login_method": "cmdline",
  "auto_terminate_on_success": false,
  "max_retries": 3,
  "retry_check_delay": 25,
  "splash_timeout": 40
}
```

- [ ] **Step 5: Create `accounts.example.txt`**

```text
# Satu akun per baris: username,password
# Baris kosong dan baris diawali '#' diabaikan.
# Salin file ini menjadi accounts.txt lalu isi akun Anda.
contoh_user1,contoh_password1
contoh_user2,contoh_password2
```

- [ ] **Step 6: Create empty package files**

Create `src/__init__.py`, `src/ui/__init__.py`, and `tests/__init__.py` each as empty files.

- [ ] **Step 7: Create `README.md`** (skeleton — expanded in Task 16)

```markdown
# Steam Multi-Box Launcher

Aplikasi GUI Windows untuk menjalankan beberapa akun Steam milik sendiri secara
terisolasi di profil Sandboxie, dengan auto-login bergiliran.

Lihat `docs/superpowers/specs/` untuk desain lengkap. Petunjuk pemakaian menyusul.
```

- [ ] **Step 8: Verify pytest runs**

Run: `python -m pytest -v`
Expected: exit code 5 (`no tests ran`) — confirms pytest is installed and configured. If pytest is missing, run `pip install -r requirements.txt` first.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "chore: project scaffold for steam-multibox"
```

---

## Task 2: `config.py` — load/save/validate configuration

**Files:**
- Create: `src/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.config'`

- [ ] **Step 3: Write `src/config.py`**

```python
"""Pemuatan, penyimpanan, dan validasi config.json."""
from dataclasses import dataclass, asdict, fields
import json
import os


@dataclass
class AppConfig:
    sandboxie_dir: str = ""
    steam_exe: str = ""
    accounts_file: str = "accounts.txt"
    box_prefix: str = "Steam_"
    stagger_seconds: int = 8
    login_method: str = "cmdline"
    auto_terminate_on_success: bool = False
    max_retries: int = 3
    retry_check_delay: int = 25
    splash_timeout: int = 40


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
    if cfg.splash_timeout < 0:
        errors.append("splash_timeout tidak boleh negatif")
    return errors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS — 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add config load/save/validate"
```

---

## Task 3: `accounts.py` — read accounts.txt, write fail.txt

**Files:**
- Create: `src/accounts.py`
- Test: `tests/test_accounts.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_accounts.py
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
    p.write_text("user1,pass1\nbroken_line_no_comma\n", encoding="utf-8")
    accounts, errors = read_accounts(str(p))
    assert len(accounts) == 1
    assert len(errors) == 1
    assert "Baris 2" in errors[0]


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_accounts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.accounts'`

- [ ] **Step 3: Write `src/accounts.py`**

```python
"""Membaca accounts.txt dan menulis fail.txt."""
from dataclasses import dataclass
import os


@dataclass
class Account:
    username: str
    password: str
    line_no: int


def read_accounts(path: str) -> tuple[list[Account], list[str]]:
    """Baca file kredensial. Kembalikan (daftar akun valid, daftar pesan error)."""
    if not os.path.exists(path):
        return [], [f"File akun tidak ditemukan: {path}"]

    accounts: list[Account] = []
    errors: list[str] = []
    with open(path, encoding="utf-8") as f:
        for i, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "," not in line:
                errors.append(f"Baris {i}: format harus 'username,password'")
                continue
            user, _, pw = line.partition(",")
            user, pw = user.strip(), pw.strip()
            if not user or not pw:
                errors.append(f"Baris {i}: username atau password kosong")
                continue
            accounts.append(Account(user, pw, i))
    return accounts, errors


def write_failures(path: str, failures: list[tuple[Account, str]]) -> None:
    """Tulis akun gagal ke fail.txt. Format: 'username,password  # alasan'."""
    with open(path, "w", encoding="utf-8") as f:
        for acc, reason in failures:
            f.write(f"{acc.username},{acc.password}  # {reason}\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_accounts.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/accounts.py tests/test_accounts.py
git commit -m "feat: add accounts reader and fail.txt writer"
```

---

## Task 4: `detect.py` — auto-detect Sandboxie & Steam

**Files:**
- Create: `src/detect.py`
- Test: `tests/test_detect.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_detect.py
from unittest.mock import patch
from src import detect


def test_detect_sandboxie_from_registry():
    with patch.object(detect, "_read_reg", return_value=r"E:\Sbie"), \
         patch.object(detect, "_dir_has_tools", side_effect=lambda d: d == r"E:\Sbie"):
        assert detect.detect_sandboxie_dir() == r"E:\Sbie"


def test_detect_sandboxie_falls_back_to_known_folders():
    with patch.object(detect, "_read_reg", return_value=None), \
         patch.object(detect, "_dir_has_tools",
                      side_effect=lambda d: d == r"C:\Program Files\Sandboxie"):
        assert detect.detect_sandboxie_dir() == r"C:\Program Files\Sandboxie"


def test_detect_sandboxie_returns_none_when_not_found():
    with patch.object(detect, "_read_reg", return_value=None), \
         patch.object(detect, "_dir_has_tools", return_value=False):
        assert detect.detect_sandboxie_dir() is None


def test_detect_steam_from_registry():
    with patch.object(detect, "_read_reg", return_value=r"D:\Steam"), \
         patch("os.path.isfile", side_effect=lambda p: p == r"D:\Steam\steam.exe"):
        assert detect.detect_steam_exe() == r"D:\Steam\steam.exe"


def test_detect_steam_returns_none_when_not_found():
    with patch.object(detect, "_read_reg", return_value=None):
        assert detect.detect_steam_exe() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_detect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.detect'`

- [ ] **Step 3: Write `src/detect.py`**

```python
"""Auto-detect lokasi instalasi Sandboxie dan Steam di Windows."""
import os
import winreg

SANDBOXIE_TOOLS = ("Start.exe", "SbieIni.exe")
SANDBOXIE_FALLBACK_DIRS = (
    r"C:\Program Files\Sandboxie",
    r"C:\Program Files\Sandboxie-Plus",
)


def _read_reg(hive, subkey: str, value: str):
    """Baca satu nilai registry. Kembalikan None jika tidak ada."""
    try:
        with winreg.OpenKey(hive, subkey) as key:
            return winreg.QueryValueEx(key, value)[0]
    except OSError:
        return None


def _dir_has_tools(directory) -> bool:
    """True jika folder memuat Start.exe dan SbieIni.exe."""
    if not directory:
        return False
    return all(os.path.isfile(os.path.join(directory, t)) for t in SANDBOXIE_TOOLS)


def detect_sandboxie_dir() -> str | None:
    """Cari folder Sandboxie: registry dulu, lalu folder umum."""
    from_reg = _read_reg(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Sandboxie",
                         "InstallLocation")
    if _dir_has_tools(from_reg):
        return from_reg
    for directory in SANDBOXIE_FALLBACK_DIRS:
        if _dir_has_tools(directory):
            return directory
    return None


def detect_steam_exe() -> str | None:
    """Cari steam.exe dari registry Valve."""
    candidates = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
    )
    for hive, subkey, value in candidates:
        path = _read_reg(hive, subkey, value)
        if path:
            exe = os.path.join(str(path).replace("/", "\\"), "steam.exe")
            if os.path.isfile(exe):
                return exe
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_detect.py -v`
Expected: PASS — 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/detect.py tests/test_detect.py
git commit -m "feat: add Sandboxie and Steam auto-detection"
```

---

## Task 5: `logbus.py` — central thread-safe log buffer

**Files:**
- Create: `src/logbus.py`
- Test: `tests/test_logbus.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_logbus.py
from src.logbus import LogBus, LogEntry


def test_log_entry_format_with_username():
    entry = LogEntry("01:19:27", "info", "user1", "launching")
    assert entry.format() == "01:19:27  user1  launching"


def test_log_entry_format_without_username():
    entry = LogEntry("01:19:27", "info", "", "aplikasi mulai")
    assert entry.format() == "01:19:27  aplikasi mulai"


def test_log_appends_entry_and_returns_it():
    bus = LogBus()
    entry = bus.log("halo", username="user1", level="ok")
    assert entry.message == "halo"
    assert entry.level == "ok"
    assert bus.all_entries() == [entry]


def test_all_text_joins_formatted_entries():
    bus = LogBus()
    bus.log("baris satu", username="u1")
    bus.log("baris dua", username="u2")
    text = bus.all_text()
    assert "u1  baris satu" in text
    assert "u2  baris dua" in text
    assert text.count("\n") == 1


def test_listener_called_on_log():
    bus = LogBus()
    received = []
    bus.add_listener(received.append)
    entry = bus.log("ping")
    assert received == [entry]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_logbus.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.logbus'`

- [ ] **Step 3: Write `src/logbus.py`**

```python
"""Buffer log terpusat, aman dipanggil dari thread mana pun."""
from dataclasses import dataclass
import threading
import time


@dataclass
class LogEntry:
    timestamp: str
    level: str       # "info" | "ok" | "error"
    username: str
    message: str

    def format(self) -> str:
        prefix = f"{self.username}  " if self.username else ""
        return f"{self.timestamp}  {prefix}{self.message}"


class LogBus:
    """Menyimpan entri log dan memberi tahu listener (mis. GUI) saat ada entri baru."""

    def __init__(self):
        self._entries: list[LogEntry] = []
        self._lock = threading.Lock()
        self._listeners: list = []

    def add_listener(self, callback) -> None:
        """Daftarkan callback(entry) yang dipanggil tiap kali ada entri baru."""
        self._listeners.append(callback)

    def log(self, message: str, username: str = "", level: str = "info") -> LogEntry:
        """Tambah entri log baru dan kembalikan entri tersebut."""
        entry = LogEntry(time.strftime("%H:%M:%S"), level, username, message)
        with self._lock:
            self._entries.append(entry)
        for callback in list(self._listeners):
            callback(entry)
        return entry

    def all_entries(self) -> list[LogEntry]:
        with self._lock:
            return list(self._entries)

    def all_text(self) -> str:
        """Seluruh log sebagai satu string (sumber untuk tombol Copy All)."""
        return "\n".join(e.format() for e in self.all_entries())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_logbus.py -v`
Expected: PASS — 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/logbus.py tests/test_logbus.py
git commit -m "feat: add central log buffer"
```

---

## Task 6: `sandboxie.py` — Sandboxie command builders & runner

**Files:**
- Create: `src/sandboxie.py`
- Test: `tests/test_sandboxie.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sandboxie.py
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
    run.assert_called_once_with(sb.create_box_cmd("Steam_user1"), check=True)


def test_launch_uses_popen():
    sb = make()
    with patch("src.sandboxie.subprocess.Popen", return_value=MagicMock()) as popen:
        sb.launch("Steam_user1", r"D:\Steam\steam.exe", ["-login", "u", "p"])
    popen.assert_called_once_with(sb.launch_cmd(
        "Steam_user1", r"D:\Steam\steam.exe", ["-login", "u", "p"]))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sandboxie.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.sandboxie'`

- [ ] **Step 3: Write `src/sandboxie.py`**

```python
"""Pembungkus tool CLI Sandboxie (Start.exe, SbieIni.exe)."""
import os
import subprocess


class Sandboxie:
    """Membangun dan menjalankan perintah Sandboxie. Mendukung Classic & Plus."""

    def __init__(self, sandboxie_dir: str):
        self.start_exe = os.path.join(sandboxie_dir, "Start.exe")
        self.sbieini_exe = os.path.join(sandboxie_dir, "SbieIni.exe")

    # --- pembangun perintah (murni, mudah diuji) ---

    def create_box_cmd(self, box: str) -> list[str]:
        return [self.sbieini_exe, "set", box, "Enabled", "y"]

    def delete_box_cmd(self, box: str) -> list[str]:
        return [self.sbieini_exe, "delete", box]

    def launch_cmd(self, box: str, program: str, args: list[str] | None = None) -> list[str]:
        return [self.start_exe, f"/box:{box}", program, *(args or [])]

    def terminate_cmd(self, box: str) -> list[str]:
        return [self.start_exe, f"/box:{box}", "/terminate"]

    # --- eksekusi ---

    def create_box(self, box: str) -> None:
        """Buat/aktifkan box. Box yang sudah ada cukup di-set ulang (idempoten)."""
        subprocess.run(self.create_box_cmd(box), check=True)

    def delete_box(self, box: str) -> None:
        subprocess.run(self.delete_box_cmd(box), check=True)

    def launch(self, box: str, program: str, args: list[str] | None = None):
        """Jalankan program di dalam box. Kembalikan objek Popen."""
        return subprocess.Popen(self.launch_cmd(box, program, args))

    def terminate(self, box: str) -> None:
        """Hentikan semua proses dalam box. Data box tetap utuh."""
        subprocess.run(self.terminate_cmd(box), check=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sandboxie.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/sandboxie.py tests/test_sandboxie.py
git commit -m "feat: add Sandboxie command wrapper"
```

---

## Task 7: `steam.py` — Steam launch argument builder

**Files:**
- Create: `src/steam.py`
- Test: `tests/test_steam.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_steam.py
from src.steam import build_login_args


def test_build_login_args():
    assert build_login_args(r"D:\Steam\steam.exe", "user1", "pass1") == [
        r"D:\Steam\steam.exe", "-login", "user1", "pass1"]


def test_build_login_args_preserves_special_chars_in_password():
    args = build_login_args(r"D:\Steam\steam.exe", "user1", "p@ss w0rd")
    assert args[3] == "p@ss w0rd"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_steam.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.steam'`

- [ ] **Step 3: Write `src/steam.py`**

```python
"""Menyusun argumen peluncuran Steam (Pendekatan A: steam.exe -login)."""


def build_login_args(steam_exe: str, username: str, password: str) -> list[str]:
    """Argumen untuk login langsung: steam.exe -login <user> <pass>.

    Dipakai sebagai program+args bagi Sandboxie.launch_cmd.
    """
    return [steam_exe, "-login", username, password]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_steam.py -v`
Expected: PASS — 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/steam.py tests/test_steam.py
git commit -m "feat: add Steam login argument builder"
```

---

## Task 8: `monitor.py` — window-state classifier

**Files:**
- Create: `src/monitor.py`
- Test: `tests/test_monitor.py`

This task implements the **pure classifier** (`BoxState`, `WindowSnapshot`, `classify`).
The IO that builds a `WindowSnapshot` from real windows lives in `steam_ui.py` (Task 9).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_monitor.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_monitor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.monitor'`

- [ ] **Step 3: Write `src/monitor.py`**

```python
"""Klasifikasi keadaan box Steam dari snapshot jendela yang terdeteksi."""
from dataclasses import dataclass
from enum import Enum


class BoxState(Enum):
    LAUNCHING = "Launching"
    HEALTHY = "Healthy"
    ACCOUNT_PICKER = "Pemilih akun"
    LOGIN_FORM = "Form login"
    WAITING_2FA = "Tunggu 2FA"
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_monitor.py -v`
Expected: PASS — 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/monitor.py tests/test_monitor.py
git commit -m "feat: add box window-state classifier"
```

---

## Task 9: `steam_ui.py` — Steam window automation (pywinauto)

**Files:**
- Create: `src/steam_ui.py`
- Test: `tests/test_steam_ui.py`

This module is the IO layer for window automation. Only the pure title-matching
helper is unit-tested; the pywinauto interaction is verified during manual
integration testing (Task 16).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_steam_ui.py
from src.steam_ui import is_account_picker_title, is_login_form_title


def test_account_picker_title_recognised():
    assert is_account_picker_title("Steam") is True            # picker pakai judul "Steam"
    assert is_account_picker_title("Who's playing?") is True


def test_login_form_title_recognised():
    assert is_login_form_title("Sign in to Steam") is True


def test_unrelated_title_not_matched():
    assert is_account_picker_title("Notepad") is False
    assert is_login_form_title("Notepad") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_steam_ui.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.steam_ui'`

- [ ] **Step 3: Write `src/steam_ui.py`**

```python
"""Otomasi jendela Steam: deteksi keadaan, klik '+', isi form login.

Memakai pywinauto. Fungsi snapshot/aksi mengembalikan hasil terbaik-usaha;
kegagalan akses jendela ditangani pemanggil (controller -> konfirmasi manual).
"""
from src.monitor import WindowSnapshot

# Penanda judul/teks jendela. Dipisah agar mudah disesuaikan saat Steam berubah.
_PICKER_TITLES = ("who's playing", "steam")
_LOGIN_TITLES = ("sign in to steam",)


def is_account_picker_title(title: str) -> bool:
    return any(t in title.lower() for t in _PICKER_TITLES)


def is_login_form_title(title: str) -> bool:
    return any(t in title.lower() for t in _LOGIN_TITLES)


def _connect_desktop():
    """Ambil objek Desktop pywinauto. Dipisah agar bisa di-mock saat tes."""
    from pywinauto import Desktop
    return Desktop(backend="uia")


def snapshot_box(box: str, elapsed: float) -> WindowSnapshot:
    """Bangun WindowSnapshot dari jendela Steam yang terlihat.

    CATATAN: Sandboxie tidak memberi label box ke jendela, jadi deteksi berbasis
    judul/teks jendela Steam. Karena Run bersifat bergiliran (satu akun aktif
    pada satu waktu), hanya ada satu sesi login Steam yang sedang berproses.
    """
    snap = WindowSnapshot(elapsed=elapsed)
    try:
        desktop = _connect_desktop()
        titles = [w.window_text() for w in desktop.windows()]
    except Exception:
        return snap  # gagal akses -> snapshot kosong -> controller minta konfirmasi manual

    texts = " | ".join(titles).lower()
    if "steam" in texts and "friends" in texts:
        snap.main_window = True
    if "sign in to steam" in texts:
        snap.login_form = True
    if "who's playing" in texts:
        snap.account_picker = True
    if "steam guard" in texts:
        snap.guard_prompt = True
    if "retry" in texts or "could not connect" in texts:
        snap.retry_error = True
    if not any([snap.main_window, snap.login_form, snap.account_picker,
                snap.guard_prompt, snap.retry_error]):
        snap.splash_only = True
    return snap


def click_add_account() -> bool:
    """Klik tombol '+' di layar pemilih akun. True jika berhasil."""
    try:
        desktop = _connect_desktop()
        win = desktop.window(title_re=".*Steam.*")
        win.child_window(title="+", control_type="Button").click_input()
        return True
    except Exception:
        return False


def fill_login_form(username: str, password: str) -> bool:
    """Isi form 'Sign in to Steam' lalu submit. True jika berhasil."""
    try:
        desktop = _connect_desktop()
        win = desktop.window(title_re=".*Sign in to Steam.*")
        edits = win.descendants(control_type="Edit")
        if len(edits) < 2:
            return False
        edits[0].set_edit_text(username)
        edits[1].set_edit_text(password)
        win.child_window(control_type="Button", found_index=0).click_input()
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_steam_ui.py -v`
Expected: PASS — 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/steam_ui.py tests/test_steam_ui.py
git commit -m "feat: add Steam window automation layer"
```

---

## Task 10: `controller.py` — turn-based run orchestration

**Files:**
- Create: `src/controller.py`
- Test: `tests/test_controller.py`

The `Controller` orchestrates a turn-based run. To stay testable it depends on a
`driver` object with these methods (the real implementation, `SteamBoxDriver`, is
also in this module; tests pass a fake):

- `ensure_box(box)` — create box if missing
- `launch(account, box)` — launch Steam with `-login` in the box
- `terminate(box)` — terminate the box
- `poll(box, elapsed) -> BoxState` — snapshot + classify current state
- `click_add()` — handle account-picker
- `fill_login(account)` — fill the login form

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_controller.py
from src.config import AppConfig
from src.logbus import LogBus
from src.accounts import Account
from src.monitor import BoxState
from src.controller import Controller


class FakeDriver:
    """Driver palsu: 'poll' mengembalikan keadaan dari skrip yang ditentukan tes."""

    def __init__(self, states_by_box: dict[str, list]):
        self.states_by_box = states_by_box
        self.calls: list[str] = []

    def ensure_box(self, box):
        self.calls.append(f"ensure:{box}")

    def launch(self, account, box):
        self.calls.append(f"launch:{box}")

    def terminate(self, box):
        self.calls.append(f"terminate:{box}")

    def click_add(self):
        self.calls.append("click_add")

    def fill_login(self, account):
        self.calls.append(f"fill:{account.username}")

    def poll(self, box, elapsed):
        return self.states_by_box[box].pop(0)


def make_controller(driver, cfg=None):
    cfg = cfg or AppConfig(max_retries=2, retry_check_delay=0,
                           stagger_seconds=0, splash_timeout=40)
    return Controller(cfg, LogBus(), driver, sleep=lambda s: None)


def test_account_healthy_first_try_succeeds():
    driver = FakeDriver({"Steam_u1": [BoxState.HEALTHY]})
    ctrl = make_controller(driver)
    ok, reason = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is True and reason == ""
    assert "launch:Steam_u1" in driver.calls


def test_account_picker_then_login_form_then_healthy():
    driver = FakeDriver({"Steam_u1": [
        BoxState.ACCOUNT_PICKER, BoxState.LOGIN_FORM, BoxState.HEALTHY]})
    ctrl = make_controller(driver)
    ok, _ = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is True
    assert "click_add" in driver.calls
    assert "fill:u1" in driver.calls


def test_stuck_splash_retries_then_fails():
    driver = FakeDriver({"Steam_u1": [
        BoxState.STUCK_SPLASH, BoxState.STUCK_SPLASH, BoxState.STUCK_SPLASH]})
    ctrl = make_controller(driver)  # max_retries=2 -> 3 attempts total
    ok, reason = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is False
    assert "retry" in reason.lower()
    assert driver.calls.count("terminate:Steam_u1") == 3


def test_stuck_retry_then_recovers():
    driver = FakeDriver({"Steam_u1": [BoxState.STUCK_RETRY, BoxState.HEALTHY]})
    ctrl = make_controller(driver)
    ok, _ = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is True
    assert driver.calls.count("launch:Steam_u1") == 2


def test_waiting_2fa_then_healthy_does_not_terminate():
    driver = FakeDriver({"Steam_u1": [BoxState.WAITING_2FA, BoxState.HEALTHY]})
    ctrl = make_controller(driver)
    ok, _ = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is True
    assert "terminate:Steam_u1" not in driver.calls


def test_run_all_writes_failures(tmp_path, monkeypatch):
    driver = FakeDriver({
        "Steam_u1": [BoxState.HEALTHY],
        "Steam_u2": [BoxState.STUCK_SPLASH, BoxState.STUCK_SPLASH, BoxState.STUCK_SPLASH],
    })
    cfg = AppConfig(max_retries=2, retry_check_delay=0, stagger_seconds=0)
    fail_path = tmp_path / "fail.txt"
    ctrl = Controller(cfg, LogBus(), driver, sleep=lambda s: None,
                      fail_path=str(fail_path))
    summary = ctrl.run_sync([Account("u1", "p1", 1), Account("u2", "p2", 2)])
    assert summary == (1, 1)  # (sukses, gagal)
    content = fail_path.read_text(encoding="utf-8")
    assert content.startswith("u2,p2  # ")


def test_auto_terminate_on_success_terminates_healthy_box():
    driver = FakeDriver({"Steam_u1": [BoxState.HEALTHY]})
    cfg = AppConfig(max_retries=2, retry_check_delay=0, stagger_seconds=0,
                    auto_terminate_on_success=True)
    ctrl = Controller(cfg, LogBus(), driver, sleep=lambda s: None)
    ctrl.run_sync([Account("u1", "p1", 1)])
    assert "terminate:Steam_u1" in driver.calls
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_controller.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.controller'`

- [ ] **Step 3: Write `src/controller.py`**

```python
"""Orkestrasi Run bergiliran + driver IO nyata + threading untuk GUI."""
import queue
import threading
import time

from src.accounts import write_failures
from src.monitor import BoxState, classify
from src.sandboxie import Sandboxie
from src.steam import build_login_args
from src import steam_ui

# batas polling agar tidak menunggu selamanya untuk satu percobaan
_MAX_POLLS_PER_ATTEMPT = 12


class SteamBoxDriver:
    """Driver IO nyata: menggerakkan Sandboxie + Steam + otomasi jendela."""

    def __init__(self, config):
        self.config = config
        self.sandboxie = Sandboxie(config.sandboxie_dir)

    def ensure_box(self, box):
        self.sandboxie.create_box(box)

    def launch(self, account, box):
        args = build_login_args(self.config.steam_exe, account.username, account.password)
        self.sandboxie.launch(box, args[0], args[1:])

    def terminate(self, box):
        self.sandboxie.terminate(box)

    def click_add(self):
        steam_ui.click_add_account()

    def fill_login(self, account):
        steam_ui.fill_login_form(account.username, account.password)

    def poll(self, box, elapsed):
        snap = steam_ui.snapshot_box(box, elapsed)
        return classify(snap, self.config.splash_timeout)


class Controller:
    """Menjalankan akun secara bergiliran; mengirim update ke GUI lewat queue."""

    def __init__(self, config, logbus, driver, sleep=time.sleep,
                 fail_path="fail.txt", status_cb=None):
        self.config = config
        self.log = logbus
        self.driver = driver
        self._sleep = sleep
        self.fail_path = fail_path
        self.status_cb = status_cb or (lambda username, state: None)
        self.updates: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None

    # --- pemrosesan satu akun ---

    def process_account(self, account) -> tuple[bool, str]:
        """Proses satu akun sampai tuntas. Kembalikan (sukses, alasan_gagal)."""
        box = self.config.box_prefix + account.username
        self._set_status(account.username, BoxState.LAUNCHING)
        try:
            self.driver.ensure_box(box)
        except Exception as e:
            self.log.log(f"gagal membuat box: {e}", account.username, "error")
            return False, f"box gagal dibuat: {e}"

        attempts = self.config.max_retries + 1
        for attempt in range(1, attempts + 1):
            try:
                self.driver.launch(account, box)
            except Exception as e:
                self.log.log(f"gagal launch: {e}", account.username, "error")
                return False, f"launch gagal: {e}"

            outcome = self._await_login(account, box)
            if outcome == "ok":
                self.log.log("login berhasil", account.username, "ok")
                return True, ""
            if outcome == "stuck":
                self._safe_terminate(box)
                self.log.log(f"stuck -> terminate (percobaan {attempt}/{attempts})",
                             account.username, "error")
                continue

        return False, f"masih stuck setelah {self.config.max_retries} retry"

    def _await_login(self, account, box) -> str:
        """Pantau satu percobaan. Kembalikan 'ok' atau 'stuck'."""
        self._sleep(self.config.retry_check_delay)
        for _ in range(_MAX_POLLS_PER_ATTEMPT):
            state = self.driver.poll(box, self.config.retry_check_delay)
            self._set_status(account.username, state)

            if state == BoxState.HEALTHY:
                return "ok"
            if state in (BoxState.STUCK_RETRY, BoxState.STUCK_SPLASH):
                return "stuck"
            if state == BoxState.ACCOUNT_PICKER:
                self.driver.click_add()
            elif state == BoxState.LOGIN_FORM:
                self.driver.fill_login(account)
            # WAITING_2FA / LAUNCHING / UNKNOWN -> terus pantau (jangan terminate)
            self._sleep(self.config.retry_check_delay)
        return "stuck"

    def _safe_terminate(self, box):
        try:
            self.driver.terminate(box)
        except Exception as e:
            self.log.log(f"gagal terminate box: {e}", "", "error")

    # --- menjalankan semua akun (bergiliran) ---

    def run_sync(self, accounts) -> tuple[int, int]:
        """Proses semua akun berurutan. Kembalikan (jumlah_sukses, jumlah_gagal)."""
        if len(accounts) > 6:
            self.log.log(f"PERINGATAN: {len(accounts)} akun — butuh RAM/CPU besar "
                         f"untuk klien Steam sebanyak itu.", "", "error")
        failures = []
        success = 0
        for account in accounts:
            ok, reason = self.process_account(account)
            if ok:
                success += 1
                if self.config.auto_terminate_on_success:
                    box = self.config.box_prefix + account.username
                    self._safe_terminate(box)
                    self.log.log("auto-terminate setelah sukses", account.username)
            else:
                failures.append((account, reason))
            self._sleep(self.config.stagger_seconds)

        write_failures(self.fail_path, failures)
        self.log.log(f"selesai: {success} sukses, {len(failures)} gagal.", "", "ok")
        if failures:
            self.log.log(f"akun gagal dicatat di {self.fail_path}", "", "error")
        return success, len(failures)

    def run_async(self, accounts) -> None:
        """Jalankan run_sync di thread latar belakang (dipakai GUI)."""
        self._thread = threading.Thread(target=self.run_sync, args=(accounts,),
                                        daemon=True)
        self._thread.start()

    def _set_status(self, username, state: BoxState):
        self.updates.put((username, state))
        self.status_cb(username, state)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_controller.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -v`
Expected: PASS — all tests from Tasks 2-10 pass (40 tests).

- [ ] **Step 6: Commit**

```bash
git add src/controller.py tests/test_controller.py
git commit -m "feat: add turn-based run controller"
```

---

## Task 11: `ui/log_panel.py` — log panel component

**Files:**
- Create: `src/ui/log_panel.py`

GUI components are verified manually (Task 16), not via pytest.

- [ ] **Step 1: Write `src/ui/log_panel.py`**

```python
"""Panel log di sidebar: textbox read-only + tombol Copy All."""
import customtkinter as ctk

_LEVEL_COLORS = {"info": "#d6d6d6", "ok": "#3fb950", "error": "#e5534b"}


class LogPanel(ctk.CTkFrame):
    """Menampilkan entri LogBus. Teks bisa diseleksi; Copy All menyalin semua."""

    def __init__(self, master, logbus):
        super().__init__(master)
        self.logbus = logbus

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(header, text="LOG", font=("Segoe UI", 11, "bold")).pack(side="left")
        ctk.CTkButton(header, text="Copy All", width=80, height=24,
                      command=self._copy_all).pack(side="right")

        self.textbox = ctk.CTkTextbox(self, font=("Consolas", 11), wrap="word")
        self.textbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.textbox.configure(state="disabled")
        for level, color in _LEVEL_COLORS.items():
            self.textbox.tag_config(level, foreground=color)

        logbus.add_listener(self._on_entry)

    def _on_entry(self, entry):
        """Dipanggil dari thread mana pun -> jadwalkan ke thread GUI."""
        self.after(0, self._append, entry)

    def _append(self, entry):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", entry.format() + "\n", entry.level)
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def _copy_all(self):
        self.clipboard_clear()
        self.clipboard_append(self.logbus.all_text())
```

- [ ] **Step 2: Smoke-test the import**

Run: `python -c "import customtkinter; from src.ui.log_panel import LogPanel; print('ok')"`
Expected: prints `ok`. If `customtkinter` is missing, run `pip install -r requirements.txt`.

- [ ] **Step 3: Commit**

```bash
git add src/ui/log_panel.py
git commit -m "feat: add log panel UI component"
```

---

## Task 12: `ui/box_list.py` — account/box status list

**Files:**
- Create: `src/ui/box_list.py`

- [ ] **Step 1: Write `src/ui/box_list.py`**

```python
"""Daftar box di area kanan: satu baris per akun, dengan status berwarna."""
import customtkinter as ctk

from src.monitor import BoxState

_STATE_COLOR = {
    BoxState.LAUNCHING: "#7a7a7a",
    BoxState.HEALTHY: "#3fb950",
    BoxState.ACCOUNT_PICKER: "#d6a532",
    BoxState.LOGIN_FORM: "#d6a532",
    BoxState.WAITING_2FA: "#d6a532",
    BoxState.STUCK_RETRY: "#3a8fd0",
    BoxState.STUCK_SPLASH: "#e5534b",
    BoxState.UNKNOWN: "#e5534b",
}


class BoxRow(ctk.CTkFrame):
    """Satu baris akun. Klik baris untuk memilih; tombol 🗑 menghapus box baris ini."""

    def __init__(self, master, username, box_name, on_select, on_delete):
        super().__init__(master, fg_color="#242424")
        self.username = username
        self.selected = False
        self._on_select = on_select

        self.dot = ctk.CTkLabel(self, text="●", width=20, text_color="#7a7a7a")
        self.dot.pack(side="left", padx=(10, 6), pady=8)
        self.name_lbl = ctk.CTkLabel(self, text=username, font=("Segoe UI", 12, "bold"))
        self.name_lbl.pack(side="left")
        self.box_lbl = ctk.CTkLabel(self, text=f"  {box_name}", font=("Segoe UI", 10),
                                    text_color="#9a9a9a")
        self.box_lbl.pack(side="left")

        # tombol hapus per-baris — TIDAK ikut memicu pemilihan baris
        self.del_btn = ctk.CTkButton(self, text="🗑", width=32, fg_color="#5a2a28",
                                     hover_color="#743532",
                                     command=lambda: on_delete(self.username))
        self.del_btn.pack(side="right", padx=(4, 10))
        self.badge = ctk.CTkLabel(self, text="-", font=("Segoe UI", 11),
                                  text_color="#9a9a9a")
        self.badge.pack(side="right", padx=4)

        # hanya widget non-tombol yang memicu pemilihan baris saat diklik
        for w in (self, self.dot, self.name_lbl, self.box_lbl, self.badge):
            w.bind("<Button-1>", lambda e: self._on_select(self.username))

    def set_state(self, state: BoxState):
        color = _STATE_COLOR.get(state, "#7a7a7a")
        self.dot.configure(text_color=color)
        self.badge.configure(text=state.value, text_color=color)

    def set_selected(self, selected: bool):
        self.selected = selected
        self.configure(fg_color="#2f4a63" if selected else "#242424")


class BoxList(ctk.CTkScrollableFrame):
    """Kumpulan BoxRow. Menyediakan akses ke akun terpilih.

    `on_delete` adalah callback(username) yang dipanggil oleh tombol 🗑 tiap baris.
    """

    def __init__(self, master, box_prefix, on_delete):
        super().__init__(master, label_text="Akun / Status Box")
        self.box_prefix = box_prefix
        self._on_delete = on_delete
        self.rows: dict[str, BoxRow] = {}
        self.selected: str | None = None

    def set_accounts(self, usernames: list[str]):
        for row in self.rows.values():
            row.destroy()
        self.rows.clear()
        self.selected = None
        for username in usernames:
            row = BoxRow(self, username, self.box_prefix + username,
                         self._select, self._on_delete)
            row.pack(fill="x", pady=3, padx=2)
            self.rows[username] = row

    def _select(self, username):
        for name, row in self.rows.items():
            row.set_selected(name == username)
        self.selected = username

    def update_status(self, username, state: BoxState):
        if username in self.rows:
            self.rows[username].set_state(state)
```

- [ ] **Step 2: Smoke-test the import**

Run: `python -c "from src.ui.box_list import BoxList; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add src/ui/box_list.py
git commit -m "feat: add box status list UI component"
```

---

## Task 13: `ui/settings_dialog.py` — settings dialog with Browse

**Files:**
- Create: `src/ui/settings_dialog.py`

- [ ] **Step 1: Write `src/ui/settings_dialog.py`**

```python
"""Dialog Pengaturan: path (dengan Browse) + angka, disimpan ke config.json."""
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

from src.config import save_config, validate_config
from src.detect import SANDBOXIE_TOOLS


class SettingsDialog(ctk.CTkToplevel):
    """Modal pengaturan. Memanggil on_saved(config) setelah simpan sukses."""

    def __init__(self, master, config, config_path, on_saved):
        super().__init__(master)
        self.title("Pengaturan")
        self.geometry("560x420")
        self.config_obj = config
        self.config_path = config_path
        self.on_saved = on_saved
        self.grab_set()

        self._path_vars: dict[str, ctk.StringVar] = {}
        self._num_vars: dict[str, ctk.StringVar] = {}

        self._add_path_row("Folder Sandboxie", "sandboxie_dir", folder=True)
        self._add_path_row("Path steam.exe", "steam_exe", folder=False)
        self._add_path_row("File accounts.txt", "accounts_file", folder=False)

        for field in ("stagger_seconds", "max_retries", "retry_check_delay",
                       "splash_timeout"):
            self._add_num_row(field)

        ctk.CTkButton(self, text="Simpan", command=self._save).pack(pady=14)

    def _add_path_row(self, label, field, folder):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(row, text=label, width=140, anchor="w").pack(side="left")
        var = ctk.StringVar(value=getattr(self.config_obj, field))
        self._path_vars[field] = var
        ctk.CTkEntry(row, textvariable=var).pack(side="left", fill="x",
                                                 expand=True, padx=6)
        ctk.CTkButton(row, text="Browse...", width=80,
                      command=lambda: self._browse(var, folder)).pack(side="left")

    def _add_num_row(self, field):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row, text=field, width=140, anchor="w").pack(side="left")
        var = ctk.StringVar(value=str(getattr(self.config_obj, field)))
        self._num_vars[field] = var
        ctk.CTkEntry(row, textvariable=var, width=80).pack(side="left", padx=6)

    def _browse(self, var, folder):
        path = filedialog.askdirectory() if folder else filedialog.askopenfilename()
        if path:
            var.set(os.path.normpath(path))

    def _save(self):
        cfg = self.config_obj
        cfg.sandboxie_dir = self._path_vars["sandboxie_dir"].get().strip()
        cfg.steam_exe = self._path_vars["steam_exe"].get().strip()
        cfg.accounts_file = self._path_vars["accounts_file"].get().strip()

        # validasi path
        if cfg.sandboxie_dir and not all(
                os.path.isfile(os.path.join(cfg.sandboxie_dir, t))
                for t in SANDBOXIE_TOOLS):
            messagebox.showerror("Pengaturan",
                                 "Folder Sandboxie tidak memuat Start.exe & SbieIni.exe.")
            return
        if cfg.steam_exe and not os.path.isfile(cfg.steam_exe):
            messagebox.showerror("Pengaturan", "steam.exe tidak ditemukan.")
            return

        try:
            for field, var in self._num_vars.items():
                setattr(cfg, field, int(var.get()))
        except ValueError:
            messagebox.showerror("Pengaturan", "Nilai angka tidak valid.")
            return

        errors = validate_config(cfg)
        if errors:
            messagebox.showerror("Pengaturan", "\n".join(errors))
            return

        save_config(cfg, self.config_path)
        self.on_saved(cfg)
        self.destroy()
```

- [ ] **Step 2: Smoke-test the import**

Run: `python -c "from src.ui.settings_dialog import SettingsDialog; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add src/ui/settings_dialog.py
git commit -m "feat: add settings dialog with Browse buttons"
```

---

## Task 14: `ui/main_window.py` — main window assembly

**Files:**
- Create: `src/ui/main_window.py`

- [ ] **Step 1: Write `src/ui/main_window.py`**

```python
"""Jendela utama (Layout A): sidebar aksi + log, area kanan daftar box."""
import os
from tkinter import messagebox

import customtkinter as ctk

from src.accounts import read_accounts
from src.config import save_config
from src.controller import Controller, SteamBoxDriver
from src.detect import detect_sandboxie_dir, detect_steam_exe
from src.ui.box_list import BoxList
from src.ui.log_panel import LogPanel
from src.ui.settings_dialog import SettingsDialog


class MainWindow(ctk.CTk):
    def __init__(self, config, config_path, logbus):
        super().__init__()
        self.config_obj = config
        self.config_path = config_path
        self.logbus = logbus
        self.title("Steam Multi-Box Launcher")
        self.geometry("960x600")

        self._build_sidebar()
        self._build_main()

        self.logbus.add_listener(lambda e: None)  # panel log sudah mendengarkan
        self._auto_detect_paths()
        self._reload_accounts()

    # --- pembangunan UI ---

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=280)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        actions = ctk.CTkFrame(sidebar, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=12)
        ctk.CTkButton(actions, text="Create Boxes",
                      command=self._on_create).pack(fill="x", pady=4)
        ctk.CTkButton(actions, text="▶  Run Semua",
                      command=self._on_run).pack(fill="x", pady=4)
        ctk.CTkButton(actions, text="■  Stop / Terminate", fg_color="#333333",
                      command=self._on_stop).pack(fill="x", pady=4)
        ctk.CTkButton(actions, text="Hapus Box Terpilih", fg_color="#5a2a28",
                      command=self._on_delete).pack(fill="x", pady=4)

        self.auto_terminate = ctk.BooleanVar(
            value=self.config_obj.auto_terminate_on_success)
        ctk.CTkCheckBox(actions, text="Auto-terminate setelah login sukses",
                        variable=self.auto_terminate,
                        command=self._on_toggle_autoterm).pack(fill="x", pady=(8, 4))
        ctk.CTkButton(actions, text="Pengaturan", fg_color="#333333",
                      command=self._on_settings).pack(fill="x", pady=4)

        self.log_panel = LogPanel(sidebar, self.logbus)
        self.log_panel.pack(fill="both", expand=True)

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="left", fill="both", expand=True, padx=12, pady=12)
        self.box_list = BoxList(main, self.config_obj.box_prefix, self._delete_box)
        self.box_list.pack(fill="both", expand=True)

    # --- logika ---

    def _auto_detect_paths(self):
        if not self.config_obj.sandboxie_dir:
            found = detect_sandboxie_dir()
            if found:
                self.config_obj.sandboxie_dir = found
        if not self.config_obj.steam_exe:
            found = detect_steam_exe()
            if found:
                self.config_obj.steam_exe = found
        save_config(self.config_obj, self.config_path)
        if not self.config_obj.sandboxie_dir or not self.config_obj.steam_exe:
            self.logbus.log("Sandboxie/Steam belum terdeteksi — buka Pengaturan "
                            "untuk Browse manual.", "", "error")

    def _reload_accounts(self):
        accounts, errors = read_accounts(self.config_obj.accounts_file)
        for err in errors:
            self.logbus.log(err, "", "error")
        self._accounts = accounts
        self.box_list.set_accounts([a.username for a in accounts])

    def _make_controller(self) -> Controller:
        driver = SteamBoxDriver(self.config_obj)
        fail_path = os.path.join(
            os.path.dirname(os.path.abspath(self.config_obj.accounts_file)) or ".",
            "fail.txt")
        return Controller(self.config_obj, self.logbus, driver, fail_path=fail_path,
                          status_cb=self._on_status)

    def _on_status(self, username, state):
        self.after(0, self.box_list.update_status, username, state)

    def _paths_ok(self) -> bool:
        if not self.config_obj.sandboxie_dir or not self.config_obj.steam_exe:
            messagebox.showerror("Path belum lengkap",
                                 "Set folder Sandboxie & steam.exe di Pengaturan.")
            return False
        return True

    # --- handler tombol ---

    def _on_create(self):
        if not self._paths_ok():
            return
        driver = SteamBoxDriver(self.config_obj)
        for acc in self._accounts:
            box = self.config_obj.box_prefix + acc.username
            try:
                driver.ensure_box(box)
                self.logbus.log("box siap", acc.username, "ok")
            except Exception as e:
                self.logbus.log(f"gagal buat box: {e}", acc.username, "error")

    def _on_run(self):
        if not self._paths_ok() or not self._accounts:
            return
        self._make_controller().run_async(self._accounts)

    def _on_stop(self):
        if not self.config_obj.sandboxie_dir:
            return
        driver = SteamBoxDriver(self.config_obj)
        for acc in self._accounts:
            box = self.config_obj.box_prefix + acc.username
            try:
                driver.terminate(box)
            except Exception:
                pass
        self.logbus.log("semua box di-terminate.", "", "ok")

    def _on_delete(self):
        """Handler tombol sidebar 'Hapus Box Terpilih' — pakai baris terpilih."""
        username = self.box_list.selected
        if not username:
            messagebox.showinfo("Hapus Box", "Pilih sebuah box dulu.")
            return
        self._delete_box(username)

    def _delete_box(self, username):
        """Logika hapus box bersama — dipakai tombol sidebar & tombol 🗑 per-baris."""
        if not self.config_obj.sandboxie_dir:
            messagebox.showerror("Hapus Box", "Folder Sandboxie belum di-set.")
            return
        box = self.config_obj.box_prefix + username
        if not messagebox.askyesno("Hapus Box",
                                   f"Hapus box '{box}' beserta datanya?"):
            return
        try:
            SteamBoxDriver(self.config_obj).sandboxie.delete_box(box)
            self.logbus.log(f"box {box} dihapus.", username, "ok")
        except Exception as e:
            self.logbus.log(f"gagal hapus box: {e}", username, "error")

    def _on_toggle_autoterm(self):
        self.config_obj.auto_terminate_on_success = self.auto_terminate.get()
        save_config(self.config_obj, self.config_path)

    def _on_settings(self):
        SettingsDialog(self, self.config_obj, self.config_path, self._on_settings_saved)

    def _on_settings_saved(self, new_config):
        self.config_obj = new_config
        self.box_list.box_prefix = new_config.box_prefix
        self._reload_accounts()
        self.logbus.log("pengaturan disimpan.", "", "ok")
```

- [ ] **Step 2: Smoke-test the import**

Run: `python -c "from src.ui.main_window import MainWindow; print('ok')"`
Expected: prints `ok`

- [ ] **Step 3: Commit**

```bash
git add src/ui/main_window.py
git commit -m "feat: add main window assembly"
```

---

## Task 15: `app.py` — application entry point

**Files:**
- Create: `app.py`

- [ ] **Step 1: Write `app.py`**

```python
"""Entry point Steam Multi-Box Launcher."""
import os
import shutil

import customtkinter as ctk

from src.config import load_config
from src.logbus import LogBus
from src.ui.main_window import MainWindow

CONFIG_PATH = "config.json"
CONFIG_EXAMPLE = "config.example.json"


def main():
    # buat config.json dari contoh saat pertama kali dijalankan
    if not os.path.exists(CONFIG_PATH) and os.path.exists(CONFIG_EXAMPLE):
        shutil.copyfile(CONFIG_EXAMPLE, CONFIG_PATH)

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    config = load_config(CONFIG_PATH)
    logbus = LogBus()
    app = MainWindow(config, CONFIG_PATH, logbus)
    logbus.log("aplikasi siap.", "", "ok")
    app.mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the full suite still passes**

Run: `python -m pytest -v`
Expected: PASS — all 40 tests pass.

- [ ] **Step 3: Verify the app launches**

Run: `python app.py`
Expected: GUI window opens with sidebar (4 buttons + checkbox + Pengaturan + LOG panel)
and an empty/populated box list. Close the window to end.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat: add application entry point"
```

---

## Task 16: README & manual integration test checklist

**Files:**
- Modify: `README.md`
- Create: `docs/MANUAL-TEST.md`

- [ ] **Step 1: Replace `README.md`**

```markdown
# Steam Multi-Box Launcher

Aplikasi GUI Windows untuk menjalankan beberapa akun Steam **milik sendiri**
secara terisolasi di profil Sandboxie, dengan auto-login bergiliran.

## Prasyarat

- **Sandboxie** (Classic atau Plus) terinstal — unduh dari
  `github.com/sandboxie-plus/Sandboxie`.
- **Steam** terinstal.
- **Python 3.10+**.

## Instalasi

```
pip install -r requirements.txt
```

## Pemakaian

1. Salin `accounts.example.txt` menjadi `accounts.txt`, isi `username,password`
   tiap akun (satu per baris).
2. Jalankan: `python app.py`
3. Jika path Sandboxie/Steam tidak terdeteksi otomatis, buka **Pengaturan** dan
   gunakan **Browse** untuk menunjuk lokasinya (boleh di drive mana pun).
4. **Create Boxes** untuk membuat profil Sandboxie.
5. **Run Semua** untuk login bergiliran. Approve prompt Steam Guard 2FA secara
   manual di tiap jendela Steam.
6. Akun yang gagal dicatat di `fail.txt`.

## Keamanan

`accounts.txt` dan `fail.txt` memuat password dalam teks biasa. Batasi izin akses
file tersebut. Keduanya sudah masuk `.gitignore`.

## Batasan

Tidak men-generate kode 2FA, tidak menyimpan shared secret, tidak membuat akun.
Hanya untuk akun milik sendiri.
```

- [ ] **Step 2: Create `docs/MANUAL-TEST.md`**

```markdown
# Manual Integration Test

Lakukan dengan **1 akun** dulu sebelum memakai banyak akun.

## Persiapan
- [ ] Sandboxie & Steam terinstal.
- [ ] `accounts.txt` berisi 1 akun valid milik sendiri.

## Tes
- [ ] `python app.py` — jendela terbuka, Layout A tampil benar.
- [ ] Path Sandboxie & Steam terisi otomatis (atau isi via Pengaturan > Browse).
- [ ] **Create Boxes** — log menunjukkan "box siap"; box muncul di Sandboxie.
- [ ] **Run Semua** — jendela Steam muncul di dalam box.
- [ ] Jika muncul layar pemilih akun, aplikasi menekan "+" otomatis.
- [ ] Form login terisi otomatis.
- [ ] Prompt Steam Guard muncul — approve manual; status box jadi "Healthy".
- [ ] Panel log: tombol **Copy All** menyalin seluruh log; teks bisa diseleksi.
- [ ] Centang **Auto-terminate setelah login sukses**, jalankan lagi — box
      ter-terminate begitu login sukses.
- [ ] Akun salah/gagal tercatat di `fail.txt` dengan format `username,password  # alasan`.
- [ ] **Stop / Terminate** menutup Steam tetapi data box tetap ada.
- [ ] **Hapus Box Terpilih** meminta konfirmasi lalu menghapus box.
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/MANUAL-TEST.md
git commit -m "docs: add README and manual test checklist"
```

---

## Self-Review Notes

**Spec coverage check:**
- Prasyarat (spec §2) → README Task 16 ✓
- GUI Layout A, sidebar+log, checkbox (spec §4.1) → Tasks 11, 14 ✓
- config.json fields incl. `auto_terminate_on_success` (spec §4.2) → Task 2 ✓
- `fail.txt` (spec §4.2) → Task 3 + Task 10 ✓
- Modul (spec §4.3) → Tasks 2-15, one task per module ✓
- Auto-detect + Browse (spec §4.4) → Tasks 4, 13 ✓
- Threading via queue + `after()` (spec §4.5) → Task 10 (`run_async`), Tasks 11/14 (`after`) ✓
- Turn-based Run + retry + picker/2FA handling (spec §5.3) → Task 10 ✓
- State classification (spec §5.3.1) → Task 8 ✓
- Stop/Terminate, Hapus Box (spec §5.4, §5.5) → Task 14 ✓
- Panel Log + Copy All (spec §5.6) → Task 11 ✓
- Security / .gitignore (spec §7) → Task 1 ✓
- Testing (spec §9) → tests in Tasks 2-10; manual checklist Task 16 ✓

**Type consistency:** `BoxState`/`WindowSnapshot` defined in Task 8 are used consistently
in Tasks 9, 10, 12. `Account` (Task 3) used in Tasks 10, 14. `AppConfig` (Task 2) used
throughout. Driver interface (`ensure_box`, `launch`, `terminate`, `poll`, `click_add`,
`fill_login`) matches between `FakeDriver` (Task 10 test) and `SteamBoxDriver` (Task 10).

No placeholders remain.
