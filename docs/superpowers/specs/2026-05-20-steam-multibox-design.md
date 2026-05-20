# Steam Multi-Box Launcher — Design Spec

**Tanggal:** 2026-05-20
**Status:** Disetujui (siap masuk tahap rencana implementasi)

## 1. Tujuan & Konteks

Aplikasi desktop GUI (Windows, Python + CustomTkinter) untuk mengotomasi penggunaan
beberapa akun Steam **milik sendiri/keluarga** di satu PC, dengan tiap akun berjalan
terisolasi di dalam profil (box) Sandboxie.

Aplikasi melakukan:

1. Auto-create profil Sandboxie untuk tiap akun.
2. Menjalankan Steam di tiap profil dengan auto-login (mengisi username & password).
3. Memantau tiap profil dan otomatis menangani box yang "stuck" (terminate + relaunch).
4. Menampilkan status tiap box dan log kejadian secara real-time di GUI.

### Batasan (di luar lingkup — sengaja tidak dibangun)

- **Tidak** men-generate kode Steam Guard 2FA. Prompt 2FA di-approve manual oleh pengguna.
- **Tidak** menyimpan/membaca shared secret atau maFile.
- **Tidak** membuat akun Steam. Akun harus sudah ada dan milik pengguna.
- **Tidak** membundel Sandboxie atau Steam — keduanya prasyarat (lihat §2).

## 2. Prasyarat

Harus sudah terpasang di PC target sebelum aplikasi dipakai:

- **Sandboxie** — edisi Classic maupun Plus didukung (keduanya memakai engine, tool CLI,
  dan format `Sandboxie.ini` yang sama). Versi open-source komunitas (Sandboxie-Plus)
  diunduh gratis dari rilis resmi `github.com/sandboxie-plus/Sandboxie`.
- **Steam** — `steam.exe` harus sudah terpasang.
- **Python 3.10+** beserta dependensi di `requirements.txt`.

Aplikasi hanya berperan sebagai lapisan otomasi di atas Sandboxie & Steam yang sudah ada.

## 3. Keputusan Desain

| Topik | Keputusan |
|---|---|
| Konteks penggunaan | Akun pribadi/keluarga milik sendiri |
| Jumlah akun | 7+ (aplikasi memberi peringatan resource jika > 6) |
| Mekanisme login | Aplikasi isi username + password; 2FA di-approve manual oleh pengguna |
| Pendekatan login | A (`steam.exe -login`) sebagai utama + UI automation untuk picker & fallback |
| Penyimpanan kredensial | File teks biasa (`accounts.txt`), pilihan pengguna — disertai peringatan keamanan |
| Bahasa/stack | Python + CustomTkinter (GUI desktop) |
| Edisi Sandboxie | Classic & Plus — deteksi berbasis menemukan `Start.exe`+`SbieIni.exe`, bukan edisi |
| Path instalasi | Bisa di drive mana pun — auto-detect + tombol Browse manual |
| Deteksi "stuck" | Auto-deteksi jendela + fallback konfirmasi manual |
| Layar pemilih akun | Selalu klik `+` lalu login akun box (abaikan akun terwarisi dari host) |
| Alur Run | Bergiliran — satu akun diproses tuntas (sukses/gagal) sebelum akun berikutnya |
| Pengelolaan jendela Steam | Dibiarkan apa adanya — tanpa auto-minimize/tile |
| Akun gagal | Dicatat ke `fail.txt`, format `username,password  # alasan` |
| Auto-terminate setelah sukses | Opsional (checkbox) — bila aktif, box di-terminate begitu login sukses lalu lanjut akun berikutnya |

## 4. Arsitektur

### 4.1 Tampilan GUI (Layout A)

Jendela tunggal CustomTkinter (tema gelap), dua area:

- **Sidebar kiri:**
  - Tombol aksi: **Create Boxes**, **Run Semua**, **Stop / Terminate**, **Hapus Box Terpilih**.
  - Tombol **Pengaturan** (buka dialog Pengaturan, §4.4).
  - Checkbox **"Auto-terminate setelah login sukses"** (dekat tombol Run) — bila dicentang,
    tiap box di-terminate begitu berhasil login lalu lanjut akun berikutnya. Status tersimpan
    di `config.json`.
  - **Panel Log** di bawah: widget teks read-only, entri = `timestamp + username + pesan`,
    warna untuk error/sukses. Teks bisa diseleksi untuk copy manual (Ctrl+C).
    Tombol **Copy All** menyalin seluruh isi buffer log ke clipboard.
- **Area kanan:** daftar box. Tiap baris: username, nama box, titik status berwarna,
  badge keadaan (Healthy / Tunggu 2FA / Retry (n/m) / Stuck / Launching / dll), dan
  tombol hapus kecil (🗑) untuk menghapus box pada baris itu (dengan konfirmasi).
  Klik baris = pilih box (untuk tombol "Hapus Box Terpilih" di sidebar).

### 4.2 File konfigurasi

- **`config.json`** — dibuat dari `config.example.json`, dapat disunting lewat dialog
  Pengaturan. Berisi:
  - `sandboxie_dir` — folder instalasi Sandboxie (memuat `Start.exe` & `SbieIni.exe`).
  - `steam_exe` — path `steam.exe`.
  - `accounts_file` — path file kredensial (default `accounts.txt`).
  - `box_prefix` — prefix nama box (default `Steam_`).
  - `stagger_seconds` — jeda singkat antar akun pada alur bergiliran (default `8`).
  - `login_method` — `"cmdline"` (Pendekatan A) atau `"ui"` (paksa UI automation). Default `"cmdline"`.
  - `auto_terminate_on_success` — bila `true`, box di-terminate begitu login sukses sebelum lanjut akun berikutnya. Default `false`. Disetel lewat checkbox di sidebar.
  - `max_retries` — batas percobaan ulang per box (default `3`).
  - `retry_check_delay` — jeda sebelum mengecek keadaan box (default `25` detik).
  - `splash_timeout` — batas waktu deteksi "stuck splash" (default `40` detik).

- **`accounts.txt`** — daftar kredensial plaintext, satu baris per akun: `username,password`.
  Baris kosong & diawali `#` diabaikan. Tercantum dalam `.gitignore`.

- **`fail.txt`** — dihasilkan otomatis di folder yang sama dengan `accounts.txt`. Memuat akun
  yang gagal pada Run terakhir, format `username,password  # alasan`. Ditimpa ulang tiap
  Run dimulai. Memuat password, jadi ikut `.gitignore` & diperlakukan seaman `accounts.txt`.

### 4.3 Modul

| Modul | Tugas | Dependensi |
|---|---|---|
| `app.py` | Entry point — inisialisasi, bangun jendela, jalankan loop GUI | `ui`, `controller` |
| `ui/main_window.py` | Rangkai sidebar + area kanan; tombol aksi memanggil `controller` | `controller`, `logbus`, komponen ui |
| `ui/box_list.py` | Komponen daftar box + status; seleksi baris | — |
| `ui/log_panel.py` | Komponen panel log; render entri; Copy All; seleksi manual | `logbus` |
| `ui/settings_dialog.py` | Dialog Pengaturan: field + tombol Browse; validasi & simpan ke `config.json` | `config`, `detect` |
| `config.py` | Load/save & validasi `config.json` | — |
| `detect.py` | Auto-detect path Sandboxie & Steam (lihat §4.4) | — |
| `accounts.py` | Baca & validasi `accounts.txt` (laporkan nomor baris jika rusak); tulis `fail.txt` akun yang gagal | — |
| `sandboxie.py` | Buat box (`SbieIni.exe set`), launch program (`Start.exe /box:`), terminate box (`Start.exe /box:<box> /terminate`), hapus box (`SbieIni.exe delete`) | `config` |
| `steam.py` | Susun perintah launch — Pendekatan A: `steam.exe -login <user> <pass>` | `config` |
| `steam_ui.py` | UI automation Steam via `pywinauto`: (a) klik `+` di layar pemilih akun, (b) isi username/password di form login & submit | `pywinauto` |
| `monitor.py` | Pantau jendela tiap box, klasifikasi keadaan, orkestrasi retry loop | `pywinauto`, `sandboxie`, `steam_ui` |
| `controller.py` | Orkestrator — jalankan create/run/monitor di thread latar belakang; kirim update status & log ke GUI | semua modul inti |
| `logbus.py` | Buffer log terpusat — semua event masuk; GUI menampilkan; sumber data Copy All | — |

### 4.4 Auto-detect & Browse

**Auto-detect Sandboxie** (`detect.py`): cari folder yang memuat `Start.exe` + `SbieIni.exe`:
1. Registry `HKLM\SOFTWARE\Sandboxie` (`InstallLocation`) — paling andal, edisi apa pun.
2. Fallback folder umum: `C:\Program Files\Sandboxie\`, lalu `C:\Program Files\Sandboxie-Plus\`.

**Auto-detect Steam:** registry `HKCU\Software\Valve\Steam` (`SteamPath`) atau
`HKLM\SOFTWARE\WOW6432Node\Valve\Steam` (`InstallPath`).

**Browse manual** (dialog Pengaturan): karena instalasi bisa ada di drive mana pun
(`D:\`, `E:\`, dll), tiap path punya tombol **Browse...**:
- Folder Sandboxie → pilih folder; divalidasi memuat `Start.exe` & `SbieIni.exe`.
- `steam.exe` → pilih file; divalidasi file ada & bernama `steam.exe`.
- `accounts.txt` → pilih file kredensial.

Alur: saat start, auto-detect mengisi field bila ketemu. Jika tidak → field kosong +
peringatan. Hasil Browse divalidasi lalu disimpan ke `config.json` (persisten).

### 4.5 Threading

GUI berjalan di main thread. Operasi launch box + monitoring berjalan di **thread
latar belakang** (`controller.py`) agar GUI tidak freeze. Update status box & entri log
dikirim balik ke GUI lewat `queue.Queue` yang di-poll dengan `root.after()` — aman dari
race condition. Tombol aksi dinonaktifkan selama operasi berlangsung bila perlu.

## 5. Alur Kerja

### 5.1 Startup

`app.py` → load `config.json` (jika belum ada, buat dari contoh) → `detect.py` mengisi
path yang kosong → bangun jendela → render daftar box dari `accounts.txt`.

### 5.2 Create Boxes

Untuk tiap akun di `accounts.txt`: pastikan box `<box_prefix><username>` ada; jika belum,
buat via `SbieIni.exe set <box> Enabled y`. Box yang sudah ada dibiarkan. Progres ke log.

### 5.3 Run Semua

Run berjalan **bergiliran**: satu akun diproses tuntas (sukses atau gagal) sebelum
akun berikutnya. Akun yang sudah Healthy tetap berjalan sementara akun berikutnya diproses,
sehingga di akhir semua box yang sukses berjalan bersamaan.

1. Validasi config & accounts. Jika jumlah akun > 6, log peringatan resource
   (≈1.5–2+ GB RAM, beban CPU besar untuk 7+ klien Steam).
2. Kosongkan/timpa `fail.txt` untuk Run ini.
3. Untuk **tiap akun, satu per satu**:
   a. Pastikan box `<box_prefix><username>` ada (buat jika belum).
   b. Launch Steam: `Start.exe /box:<box> <steam_exe> -login <user> <pass>`.
   c. **Fase monitor** — tunggu `retry_check_delay`, lalu `monitor.py` mengklasifikasi
      keadaan box (lihat §5.3.1):
      - Stuck → `terminate_box` → launch + login ulang → ulangi hingga `max_retries`.
      - Picker → `steam_ui.py` klik `+` → form login → isi kredensial.
      - Tunggu 2FA → tunggu pengguna approve manual (akun belum dianggap selesai).
      - Ragu → tampilkan konfirmasi manual di GUI untuk box itu.
   d. Akun dianggap **selesai** saat keadaan Healthy. Akun **gagal** bila tetap stuck
      setelah `max_retries`, atau box gagal dibuat/launch → catat ke `fail.txt`
      (`username,password  # alasan`).
   e. Bila `auto_terminate_on_success` aktif **dan** akun sukses → `terminate_box`
      (data box tetap utuh) sebelum lanjut. Bila tidak aktif, box dibiarkan berjalan.
   f. Tunggu `stagger_seconds`, lalu lanjut ke akun berikutnya.
4. Status tiap box & jumlah retry diperbarui real-time di daftar box; semua kejadian ke log.
5. Setelah semua akun diproses, log ringkasan: jumlah sukses & gagal. Bila ada kegagalan,
   tunjuk lokasi `fail.txt`.

#### 5.3.1 Klasifikasi keadaan box (`monitor.py`)

| Keadaan | Ciri | Tindakan |
|---|---|---|
| Sehat | Jendela utama Steam muncul (sudah masuk) | Sukses |
| Pemilih akun | Layar "Who's playing?" — kotak akun tersimpan + tombol `+` | `steam_ui.py` klik `+` → tunggu form login → lanjut ke "Form login" |
| Form login | Form username/password tampil tapi belum terisi (`-login` tidak mengisi) | `steam_ui.py` isi username/password → submit |
| Tunggu 2FA | Prompt Steam Guard muncul | **Jangan** terminate — tunggu approve manual pengguna |
| Stuck retry | Jendela error koneksi / tombol "Retry" terdeteksi | `terminate_box` + relaunch |
| Stuck splash | Hanya splash/logo Steam setelah `splash_timeout`, tanpa jendela utama/2FA | `terminate_box` + relaunch |
| Ragu | Tidak cocok kategori mana pun | Konfirmasi manual di GUI |

Pembedaan **stuck splash** vs **tunggu 2FA** wajib akurat: box yang menunggu approve
Steam Guard tidak boleh di-terminate.

**Layar pemilih akun** muncul karena box Sandboxie mewarisi konfigurasi Steam akun asli
yang sudah login di host. Aplikasi selalu memilih `+` (tambah akun) untuk login akun yang
ditetapkan bagi box itu, bukan memakai akun terwarisi.

### 5.4 Stop / Terminate

Jalankan `Start.exe /box:<box> /terminate` untuk box terpilih (atau semua) — menghentikan
seluruh proses dalam box. **Data box tetap utuh.** Monitoring dihentikan.

### 5.5 Hapus Box

Hapus box dari `Sandboxie.ini` (`SbieIni.exe delete <box>`). Memerlukan konfirmasi
karena menghapus data box. **Berbeda dari Terminate** — Terminate hanya menghentikan proses.

Dua cara memicu: tombol sidebar **"Hapus Box Terpilih"** (memakai baris yang dipilih),
atau tombol hapus kecil (🗑) pada baris box yang bersangkutan. Keduanya memanggil logika
hapus yang sama.

### 5.6 Panel Log

Semua event (`logbus.py`) tampil di panel log sidebar secara real-time. Teks dapat
diseleksi untuk copy manual; tombol **Copy All** menyalin seluruh buffer ke clipboard.

## 6. Penanganan Error

- Sandboxie/Steam tidak ditemukan & path kosong → peringatan di GUI, arahkan ke dialog
  Pengaturan untuk Browse manual; tombol aksi dinonaktifkan sampai path valid.
- `accounts.txt` hilang/rusak → log nomor baris bermasalah; akun rusak dilewati.
- Gagal membuat box atau launch satu akun → catat error di log, **lanjutkan** akun lain.
- `pywinauto` gagal mengakses jendela → turunkan ke konfirmasi manual untuk box itu.
- Operasi background gagal total → status box di-set "Error", dilaporkan di log.

## 7. Keamanan

- `accounts.txt` plaintext: siapa pun yang membaca file mendapat semua password.
  Aplikasi menampilkan peringatan dan menyarankan membatasi izin NTFS file tersebut.
- `.gitignore` memuat `config.json`, `accounts.txt`, dan `fail.txt` agar tidak pernah ter-commit.
- `fail.txt` juga memuat password — diperlakukan seaman `accounts.txt`.
- Pendekatan A: password sempat terlihat di daftar proses selama beberapa detik saat launch
  (keterbatasan `steam.exe -login` yang diketahui & diterima).

## 8. Struktur File

```
auto create profile sandboxie/
├── app.py                      (entry point GUI)
├── config.example.json
├── accounts.example.txt
├── .gitignore                  (config.json, accounts.txt, fail.txt)
├── README.md
├── requirements.txt            (customtkinter, pywinauto)
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── detect.py
│   ├── accounts.py
│   ├── sandboxie.py
│   ├── steam.py
│   ├── steam_ui.py
│   ├── monitor.py
│   ├── controller.py
│   ├── logbus.py
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py
│       ├── box_list.py
│       ├── log_panel.py
│       └── settings_dialog.py
├── tests/
│   ├── test_accounts.py        (parsing + baris rusak)
│   ├── test_config.py          (load/save + validasi)
│   ├── test_detect.py          (auto-detect, registry & folder di-mock)
│   ├── test_steam.py           (konstruksi perintah launch -login)
│   ├── test_monitor.py         (klasifikasi keadaan + logika retry, deteksi di-mock)
│   └── test_controller.py      (orkestrasi, modul inti di-mock)
└── docs/
    ├── superpowers/specs/2026-05-20-steam-multibox-design.md
    └── mockups/layout-mockup.html
```

## 9. Testing

- Framework: `pytest`.
- Unit test fokus pada logika murni: parsing kredensial, load/validasi config, auto-detect
  (registry & folder di-mock), konstruksi string perintah (`-login`, `/box:`, `/terminate`,
  `delete`), klasifikasi keadaan box, dan logika retry.
- Interaksi jendela (`pywinauto`) dan eksekusi Sandboxie/Steam di-mock.
- `controller.py` diuji dengan modul inti di-mock untuk memverifikasi orkestrasi & threading.
- GUI (CustomTkinter) diuji manual.
- Pengujian integrasi dilakukan manual oleh pengguna dengan 1 box terlebih dulu.
