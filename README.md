# Steam Multi-Box Launcher

Aplikasi GUI Windows untuk menjalankan beberapa akun Steam **milik sendiri** secara terisolasi
di profil Sandboxie, dengan auto-login bergiliran, verifikasi akun, auto-save Remember Me,
retry pintar, dan notifikasi Discord opsional.

> 📚 **Dokumentasi lengkap (HTML) ada di folder [`docs/`](docs)**:
> [README](docs/README.html) · [Tata Cara Pakai](docs/USAGE.html) · [Handoff](docs/HANDOFF.html) · [Manual Test](docs/MANUAL-TEST.html)
>
> GitHub tidak render HTML inline — unduh repo lalu buka file `docs/*.html` di Chrome
> untuk tampilan lengkap. Atau pakai [htmlpreview.github.io](https://htmlpreview.github.io/?https://github.com/San3080/steam-multibox/blob/main/docs/README.html).

---

## Prasyarat

- **Sandboxie** (Classic atau Plus) — [github.com/sandboxie-plus/Sandboxie](https://github.com/sandboxie-plus/Sandboxie)
- **Steam** terinstal
- **Python 3.10+**

## Instalasi

```bash
git clone https://github.com/San3080/steam-multibox.git
cd steam-multibox
pip install -r requirements.txt
```

## Quick Start

1. Salin `data/accounts.example.txt` jadi `data/accounts.txt`, isi
   `username,password` (atau `username|password`) — satu akun per baris.
2. Jalankan: `python app.py`
3. **Pengaturan** → pastikan path Sandboxie & Steam terisi (klik **Auto Find** kalau tidak).
4. Klik **Run Semua**. Tool akan minta menutup Steam host kalau jalan → **Yes**.
5. Approve prompt Steam Guard 2FA manual di tiap jendela Steam yang muncul.
6. Setelah selesai → buka box manual via SandMan → Steam **auto-login** ke akun yang sesuai.

Detail lengkap: [docs/USAGE.html](docs/USAGE.html).

## Fitur Utama

| Fitur | Penjelasan |
|---|---|
| Auto-detect Sandboxie & Steam | Registry + service path + scan semua drive |
| Run bergiliran + Stop interruptible | Tidak spam, controller bisa dihentikan cepat |
| UI form login + Remember Me | Token tersimpan → manual reopen box auto-login |
| Verifikasi akun via VDF | Baca `loginusers.vdf` + cek `MostRecent` → cocokkan ke `accounts.txt` |
| Auto recovery mismatch | Akun salah login → wipe sesi + retry sampai `max_retries+1` |
| Run Tercentang | Checkbox per-baris untuk subset akun |
| Edit Credential per box | ✏️ ubah username/password → wipe + relaunch otomatis |
| Hapus box aman | terminate → `delete_sandbox` → edit `Sandboxie.ini` |
| Tutup Steam host pre-Run | Mencegah konflik single-instance Steam |
| Silence Sandboxie popup | 16 kode SBIE non-fatal di-set di `[GlobalSettings]` |
| Discord webhook (opsional) | Notif run start/done, login sukses/gagal, edit credential |

## Keamanan

⚠️ `data/accounts.txt` & `data/fail.txt` berisi password **teks biasa**. Batasi izin
akses folder `data/` (NTFS permission). Keduanya sudah masuk `.gitignore`.

## Batasan (sengaja)

- Tidak men-generate kode Steam Guard 2FA — user approve manual.
- Tidak menyimpan `shared_secret` / maFile.
- Tidak membuat akun Steam.
- Hanya untuk akun milik sendiri (keluarga, akun alt pribadi, testing).

## Tech Stack

Python 3.10+ · CustomTkinter (GUI) · pywinauto (UI automation) · pytest · Sandboxie CLI.

**130 unit test** untuk semua modul pure-logic (config, accounts, detect, monitor,
controller, login_verify, sandboxie, host_steam, discord_webhook).

## Struktur Proyek

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
├── tests/                  pytest (130 tests)
├── data/                   accounts.txt + fail.txt (gitignored)
└── docs/                   Dokumentasi HTML lengkap
```

## Lisensi & Disclaimer

Tool ini dibuat untuk pemakaian pribadi — mengelola akun Steam **yang kamu miliki sendiri**
(akun keluarga, akun alt pribadi, akun testing). Pemakaian melanggar Steam Subscriber Agreement
(account farming, manipulation, botting) bukan tanggung jawab tool ini maupun penulisnya.
