"""Cari & buka jendela utama Sandboxie (SandMan untuk Plus, SbieCtrl untuk Classic)."""
import os
import subprocess


# Nama executable UI manajemen Sandboxie, urut prioritas.
_UI_EXES = ("SandMan.exe", "SbieCtrl.exe")


def find_sandboxie_ui(sandboxie_dir: str) -> str | None:
    """Cari path executable UI Sandboxie di folder instalasi."""
    if not sandboxie_dir:
        return None
    for name in _UI_EXES:
        candidate = os.path.join(sandboxie_dir, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def open_sandboxie_ui(sandboxie_dir: str) -> tuple[bool, str]:
    """Buka jendela manajemen Sandboxie. Mengembalikan (sukses, pesan).

    Aman dipanggil berulang — kalau UI sudah jalan, ia hanya difokuskan.
    """
    exe = find_sandboxie_ui(sandboxie_dir)
    if not exe:
        return False, "UI Sandboxie (SandMan/SbieCtrl) tidak ditemukan."
    try:
        subprocess.Popen([exe])
    except Exception as e:
        return False, f"gagal membuka {os.path.basename(exe)}: {e}"
    return True, f"{os.path.basename(exe)} dibuka."
