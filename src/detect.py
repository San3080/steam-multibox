"""Auto-detect lokasi instalasi Sandboxie dan Steam di Windows.

Strategi deteksi (urutan):
  1. Baca registry — jalur paling andal kalau aplikasi terinstal "benar".
  2. Pindai semua drive terpasang untuk sub-folder umum
     (`Program Files\\Sandboxie`, `Program Files (x86)\\Steam`, dll.) —
     menangani instalasi di drive selain C:.
"""
import os
import string
import winreg

SANDBOXIE_TOOLS = ("Start.exe", "SbieIni.exe")

# Sub-folder umum tempat orang memasang Sandboxie / Steam, relatif terhadap
# akar drive. Dipindai pada setiap drive yang terpasang.
_SANDBOXIE_SUBPATHS = (
    r"Program Files\Sandboxie",
    r"Program Files\Sandboxie-Plus",
    r"Program Files (x86)\Sandboxie",
    r"Program Files (x86)\Sandboxie-Plus",
    "Sandboxie",
    "Sandboxie-Plus",
)
_STEAM_SUBPATHS = (
    r"Program Files (x86)\Steam",
    r"Program Files\Steam",
    "Steam",
    "SteamLibrary",
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


def _fixed_drives() -> list[str]:
    """Daftar drive yang terpasang, mis. ['C:', 'D:']. Fallback ['C:'] jika gagal."""
    try:
        from ctypes import windll
        mask = windll.kernel32.GetLogicalDrives()
        return [f"{letter}:" for i, letter in enumerate(string.ascii_uppercase)
                if mask & (1 << i)]
    except Exception:
        return ["C:"]


def _dir_from_service_image_path() -> str | None:
    """Folder Sandboxie dari path service SbieSvc di registry.

    Service ini dibuat saat Sandboxie terpasang (Classic & Plus), jadi path-nya
    selalu menunjuk ke folder instalasi yang sebenarnya — di drive mana pun,
    nama folder apa pun. Lebih andal daripada SOFTWARE\\Sandboxie\\InstallLocation
    yang tidak selalu di-set.
    """
    raw = _read_reg(winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Services\SbieSvc", "ImagePath")
    if not raw:
        return None
    # ImagePath bisa berbentuk `"D:\Sandboxie\SbieSvc.exe" -arg` (berkutip)
    # atau `C:\Program Files\Sandboxie\SbieSvc.exe` (tanpa kutip, dengan spasi).
    # Untuk yang tak-berkutip, kita potong tepat setelah `.exe` agar spasi di
    # `Program Files` tidak salah dianggap pemisah argumen.
    raw = str(raw).strip()
    if raw.startswith('"'):
        end = raw.find('"', 1)
        exe = raw[1:end] if end > 0 else raw.strip('"')
    else:
        idx = raw.lower().find(".exe")
        exe = raw[:idx + 4] if idx >= 0 else raw.split(" ", 1)[0]
    folder = os.path.dirname(exe)
    return folder or None


def detect_sandboxie_dir() -> str | None:
    """Cari folder Sandboxie: registry service, registry classic, lalu scan drive."""
    from_service = _dir_from_service_image_path()
    if _dir_has_tools(from_service):
        return from_service
    from_reg = _read_reg(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Sandboxie",
                         "InstallLocation")
    if _dir_has_tools(from_reg):
        return from_reg
    for drive in _fixed_drives():
        for sub in _SANDBOXIE_SUBPATHS:
            candidate = os.path.join(drive + os.sep, sub)
            if _dir_has_tools(candidate):
                return candidate
    return None


def detect_steam_exe() -> str | None:
    """Cari steam.exe: registry Valve, lalu pindai semua drive terpasang."""
    reg_candidates = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
    )
    for hive, subkey, value in reg_candidates:
        path = _read_reg(hive, subkey, value)
        if path:
            exe = os.path.join(str(path).replace("/", "\\"), "steam.exe")
            if os.path.isfile(exe):
                return exe
    for drive in _fixed_drives():
        for sub in _STEAM_SUBPATHS:
            exe = os.path.join(drive + os.sep, sub, "steam.exe")
            if os.path.isfile(exe):
                return exe
    return None
