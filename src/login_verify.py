"""Verifikasi akun yang sedang login di Steam dengan membaca loginusers.vdf.

Sandboxie mem-virtualisasi filesystem; file Steam yang ditulis di dalam box
sebenarnya disimpan di folder box (mis.
`C:\\Sandbox\\<WindowsUser>\\<BoxName>\\drive\\C\\Program Files (x86)\\Steam\\config\\loginusers.vdf`).
File itu mencantumkan AccountName yang baru saja login.
"""
import glob
import os
import re

# Lokasi default Steam config relatif terhadap root box. Sandboxie boleh saja
# memakai ProgramFiles, ProgramFiles (x86), atau drive lain — kita coba semuanya.
_STEAM_CONFIG_SUBPATHS = (
    r"drive\C\Program Files (x86)\Steam\config\loginusers.vdf",
    r"drive\C\Program Files\Steam\config\loginusers.vdf",
    r"user\current\AppData\Local\Steam\config\loginusers.vdf",
)


def _expand_file_root_template(template: str, box: str) -> str:
    """Expand Sandboxie FileRootPath template (mis. `%SystemDrive%\\Sandbox\\%USER%\\%SANDBOX%`)
    menggantikan %USER% & %SANDBOX% lalu env vars Windows."""
    user = os.environ.get("USERNAME", "")
    text = template.replace("%USER%", user).replace("%SANDBOX%", box)
    return os.path.expandvars(text)


def _read_file_root_path_from_ini() -> str | None:
    """Ambil FileRootPath dari Sandboxie.ini. Bisa di section box-spesifik
    atau [GlobalSettings]. Return template string, atau None kalau tidak ada."""
    ini_candidates = [
        r"C:\Windows\Sandboxie.ini",
        r"C:\ProgramData\Sandboxie\Sandboxie.ini",
    ]
    for p in ini_candidates:
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "rb") as f:
                raw = f.read()
            if raw.startswith(b"\xff\xfe"):
                text = raw.decode("utf-16")
            elif raw.startswith(b"\xef\xbb\xbf"):
                text = raw.decode("utf-8-sig")
            else:
                text = raw.decode("utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("filerootpath="):
                return stripped.split("=", 1)[1].strip()
    return None


def find_box_root(box: str) -> str | None:
    """Cari folder root box di disk.

    Strategi:
      1. Baca FileRootPath dari Sandboxie.ini, expand template.
         Ini yang Sandboxie sendiri pakai, jadi paling akurat.
      2. Fallback ke path default umum (kalau .ini tidak punya entri).
    """
    template = _read_file_root_path_from_ini()
    if template:
        candidate = _expand_file_root_template(template, box)
        if os.path.isdir(candidate):
            return candidate

    user = os.environ.get("USERNAME", "")
    candidates = [
        rf"C:\Sandbox\{user}\{box}",
        rf"D:\Sandbox\{user}\{box}",
        rf"C:\Sandbox\{box}",
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return None


def find_loginusers_vdf(box_root: str) -> str | None:
    """Path loginusers.vdf yang ada di dalam box, atau None."""
    if not box_root:
        return None
    for sub in _STEAM_CONFIG_SUBPATHS:
        p = os.path.join(box_root, sub)
        if os.path.isfile(p):
            return p
    return None


def parse_account_names(vdf_text: str) -> list[str]:
    """Ambil semua nilai AccountName dari isi loginusers.vdf."""
    # Format VDF: `"AccountName"\t\t"<name>"`. Regex sederhana cukup.
    return re.findall(r'"AccountName"\s+"([^"]+)"', vdf_text)


def parse_active_account(vdf_text: str) -> str | None:
    """AccountName yang sedang aktif (MostRecent=1), atau None kalau tidak ada.

    Steam menandai akun terakhir login dengan `"MostRecent" "1"`. Ini yang
    benar-benar dipakai untuk auto-login berikutnya — jauh lebih akurat
    daripada sekadar "AccountName apa pun yang ada di file".
    """
    # Tiap blok pengguna: `"76561198..." { ... }`.
    pattern = re.compile(r'"\d+"\s*\{([^{}]*)\}', re.DOTALL)
    for m in pattern.finditer(vdf_text):
        block = m.group(1)
        if re.search(r'"MostRecent"\s+"1"', block):
            name = re.search(r'"AccountName"\s+"([^"]+)"', block)
            if name:
                return name.group(1)
    return None


def verify_login(box: str, expected_username: str) -> tuple[bool | None, str]:
    """Cek apakah `expected_username` adalah akun AKTIF di box.

    Strategi:
      1. Cari akun ber-MostRecent=1 (sesi aktif Steam). Bandingkan ke expected.
         Ini paling akurat dan menangani kasus vdf punya banyak akun cached.
      2. Kalau tidak ada MostRecent (mis. vdf masih segar), fallback ke
         "expected ada di daftar AccountName" — agar tidak false-negative.

    Mengembalikan (matched, detail):
      - (True, "...") akun aktif sesuai expected.
      - (False, "...") akun aktif berbeda dari expected — Steam login ke akun lain.
      - (None, "...") vdf belum bisa dibaca / belum berisi data.
    """
    root = find_box_root(box)
    if not root:
        return None, f"folder box tidak ditemukan untuk '{box}'"
    vdf = find_loginusers_vdf(root)
    if not vdf:
        return None, "loginusers.vdf belum ditulis Steam"
    try:
        with open(vdf, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        return None, f"gagal baca loginusers.vdf: {e}"

    expected_l = expected_username.lower()

    # 1) Cek MostRecent (akun yang sebenarnya sedang aktif).
    active = parse_active_account(text)
    if active is not None:
        if active.lower() == expected_l:
            return True, f"login terverifikasi (MostRecent): {expected_username}"
        return False, (f"akun aktif lain: {active} (diharapkan {expected_username})")

    # 2) Fallback: tidak ada MostRecent — cek apakah expected setidaknya ada.
    names = [n.lower() for n in parse_account_names(text)]
    if expected_l in names:
        return True, f"login terverifikasi: {expected_username}"
    if names:
        return False, f"login akun lain: {', '.join(names)} (diharapkan {expected_username})"
    return None, "loginusers.vdf ada tapi belum berisi akun"


def has_ssfn_token(box_root: str) -> bool:
    """True jika box punya file ssfn* — penanda Steam Guard sentry tersimpan.

    Tanpa ssfn, manual reopen box akan minta login ulang (Steam anggap device
    baru). ssfn cuma ditulis Steam saat user sign-in lewat UI form dengan
    Remember me dicentang.
    """
    if not box_root or not os.path.isdir(box_root):
        return False
    for sub in _STEAM_CONFIG_SUBPATHS:
        steam_dir = os.path.dirname(os.path.dirname(
            os.path.join(box_root, sub)))
        if glob.glob(os.path.join(steam_dir, "ssfn*")):
            return True
    return False


def enable_remember_password(box_root: str) -> bool:
    """Ubah semua RememberPassword '0' menjadi '1' di loginusers.vdf box.

    Kembalikan True kalau file dimodifikasi, False kalau tidak ada perubahan
    (file tak ada, atau memang sudah '1', atau tidak ada baris RememberPassword).
    """
    if not box_root:
        return False
    vdf = find_loginusers_vdf(box_root)
    if not vdf:
        return False
    try:
        with open(vdf, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return False
    new_text = re.sub(r'("RememberPassword"\s+)"0"', r'\1"1"', text)
    if new_text == text:
        return False
    try:
        with open(vdf, "w", encoding="utf-8") as f:
            f.write(new_text)
    except OSError:
        return False
    return True


def prime_clean_steam_config(box_root: str) -> int:
    """Bersihkan state Steam inherited dari host SEBELUM launch agar box
    benar-benar mulai dari nol untuk akun yang akan login.

    Sandboxie copy-on-read salin loginusers.vdf & config.vdf host ke box pada
    read pertama; tanpa pembersihan, box mewarisi 4-5 akun host plus token
    yang tidak cocok. Kita hapus: loginusers.vdf, config.vdf, ssfn*. File yang
    tidak ada -> silent skip.

    Mengembalikan jumlah file yang dihapus.
    """
    return wipe_steam_session(box_root)[0]


def wipe_steam_session(box_root: str) -> tuple[int, list[str]]:
    """Hapus file sesi Steam di dalam box: loginusers.vdf, config.vdf, ssfn*.

    Kembalikan (jumlah_dihapus, daftar_path_yang_dihapus).
    Aman dipanggil meski file tidak ada -- best-effort.
    """
    if not box_root or not os.path.isdir(box_root):
        return 0, []
    candidates: list[str] = []
    # File config di sub-folder config/
    for sub in _STEAM_CONFIG_SUBPATHS:
        cfg_dir = os.path.dirname(os.path.join(box_root, sub))
        for name in ("loginusers.vdf", "config.vdf"):
            candidates.append(os.path.join(cfg_dir, name))
    # ssfn* tokens di root folder Steam (satu level di atas config/)
    for sub in _STEAM_CONFIG_SUBPATHS:
        steam_dir = os.path.dirname(os.path.dirname(
            os.path.join(box_root, sub)))
        candidates.extend(glob.glob(os.path.join(steam_dir, "ssfn*")))

    removed: list[str] = []
    for p in candidates:
        if os.path.isfile(p):
            try:
                os.remove(p)
                removed.append(p)
            except OSError:
                pass
    return len(removed), removed
