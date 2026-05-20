# Steam Multi-Box Launcher

A Windows GUI app for running **multiple personal Steam accounts** in isolated
Sandboxie profiles, with sequential auto-login, per-account verification,
persistent Remember Me, smart retry on mismatch, and optional Discord notifications.

> 📚 **Full documentation (HTML) lives in [`docs/`](docs)**:
> [README](docs/README.html) · [Usage Guide](docs/USAGE.html) · [Handoff](docs/HANDOFF.html) · [Manual Test](docs/MANUAL-TEST.html)
>
> GitHub does not render HTML inline — clone the repo and open `docs/*.html` in
> Chrome for the full styled view. Or use
> [htmlpreview.github.io](https://htmlpreview.github.io/?https://github.com/San3080/steam-multibox/blob/main/docs/README.html).

---

## Prerequisites

- **Sandboxie** (Classic or Plus) — get it from
  [github.com/sandboxie-plus/Sandboxie](https://github.com/sandboxie-plus/Sandboxie)
- **Steam** installed
- **Python 3.10+**

## Installation

```bash
git clone https://github.com/San3080/steam-multibox.git
cd steam-multibox
pip install -r requirements.txt
```

## Quick Start

1. Copy `data/accounts.example.txt` to `data/accounts.txt`, fill it with
   `username,password` (or `username|password`) — one account per line.
2. Run: `python app.py`
3. Click **Pengaturan** (Settings) → make sure Sandboxie & Steam paths are filled
   (click **Auto Find** if not).
4. Click **Run Semua** (Run All). If a popup asks to close host Steam → **Yes**.
5. Approve the Steam Guard 2FA prompt manually in each Steam window that appears
   (if 2FA is enabled for that account).
6. After completion → open the box manually via SandMan → Steam **auto-logs in**
   to the account assigned to that box.

Step-by-step details: [docs/USAGE.html](docs/USAGE.html).

## Key Features

| Feature | What it does |
|---|---|
| Auto-detect Sandboxie & Steam | Registry + service path + scan of all drives |
| Sequential Run + interruptible Stop | No spam, controller stops within ~5s |
| UI form login + Remember Me | Token persists → manual reopen of the box auto-logs in |
| VDF-based account verification | Reads `loginusers.vdf` + checks `MostRecent` against `accounts.txt` |
| Mismatch auto-recovery | If the wrong account logged in → wipe session + retry up to `max_retries+1` |
| Per-row checkbox + Run Tercentang | Run only the accounts you check |
| Per-box Edit Credential | ✏️ change username/password → wipe + relaunch automatically |
| Safe box delete | terminate → `delete_sandbox` → edit `Sandboxie.ini` |
| Kill host Steam pre-Run | Prevents single-instance Steam from hijacking the sandbox launch |
| Silence Sandboxie popups | 16 non-fatal SBIE codes hidden via `[GlobalSettings]` |
| Discord webhook (optional) | Notifies on run start/done, login success/failure, edit credential |

## Security

⚠️ `data/accounts.txt` and `data/fail.txt` store passwords in **plain text**.
Restrict NTFS access to the `data/` folder. Both are already in `.gitignore`.

## Scope (intentional limits)

- Does **not** generate Steam Guard 2FA codes — user approves manually.
- Does **not** store `shared_secret` / maFile.
- Does **not** create Steam accounts.
- For accounts **you own** only (family, personal alts, testing).

Use that respects the Steam Subscriber Agreement is your responsibility — the tool
won't help with account farming, manipulation, or anything else that violates the
SSA.

## Tech Stack

Python 3.10+ · CustomTkinter (GUI) · pywinauto (UI automation) · pytest · Sandboxie CLI.

**130 unit tests** covering all pure-logic modules (config, accounts, detect,
monitor, controller, login_verify, sandboxie, host_steam, discord_webhook).

## Project Structure

```
.
├── app.py                  Entry point
├── src/
│   ├── config.py           Config dataclass + load/save/validate
│   ├── accounts.py         Read accounts.txt, write fail.txt
│   ├── detect.py           Auto-detect Sandboxie & Steam
│   ├── host_steam.py       Detect/kill host steam.exe
│   ├── sandman.py          Open SandMan UI
│   ├── sandboxie.py        CLI wrapper: create_box, delete_box, etc.
│   ├── steam.py            -login arg builder
│   ├── steam_ui.py         pywinauto: snapshot_box, fill_login_form
│   ├── monitor.py          BoxState + classify
│   ├── login_verify.py     VDF parsing, wipe, RememberPassword
│   ├── controller.py       SteamBoxDriver + Controller (orchestration)
│   ├── logbus.py           Thread-safe log buffer
│   ├── discord_webhook.py  Notification helpers
│   └── ui/
│       ├── main_window.py
│       ├── box_list.py
│       ├── log_panel.py
│       ├── settings_dialog.py
│       └── edit_credential_dialog.py
├── tests/                  pytest suite (130 tests)
├── data/                   accounts.txt + fail.txt (gitignored)
└── docs/                   Full HTML documentation
```

## License & Disclaimer

This tool is for personal use — managing Steam accounts **you own** (family
accounts, personal alts, testing accounts). Using it in ways that violate the
[Steam Subscriber Agreement](https://store.steampowered.com/subscriber_agreement/)
(account farming, manipulation, automated playing, etc.) is **not the
responsibility** of this tool or its author.
