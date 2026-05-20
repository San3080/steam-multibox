"""Deteksi & kill proses steam.exe di host (di luar sandbox).

Steam adalah single-instance app: kalau `steam.exe` sudah jalan, perintah baru
diteruskan ke instance yang ada — termasuk perintah dari dalam Sandboxie.
Akibatnya box "ngikut" Steam host: yang menerima login = host, bukan box.
Solusinya: pastikan tidak ada steam.exe di host sebelum Run.
"""
import subprocess


def is_host_steam_running() -> bool:
    """True kalau ada proses steam.exe di sistem (host atau sandbox, kita tidak
    bisa bedakan dari tasklist saja — pemakai dipanggil untuk mematikannya jika
    perlu sebelum Run pertama)."""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq steam.exe", "/NH"],
            stderr=subprocess.STDOUT, text=True, timeout=5)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return "steam.exe" in out.lower()


def kill_host_steam() -> tuple[bool, str]:
    """Bunuh paksa semua steam.exe (host + sandbox sekaligus).

    Dipanggil SEBELUM Run untuk memastikan instance baru di sandbox bisa start.
    Mengembalikan (sukses, pesan).
    """
    try:
        out = subprocess.run(
            ["taskkill", "/F", "/IM", "steam.exe", "/T"],
            capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return False, f"taskkill error: {e}"
    if out.returncode == 0:
        return True, "Steam host dimatikan."
    # exit 128 dari taskkill artinya tidak ada proses yang cocok — itu OK
    if "not found" in (out.stdout + out.stderr).lower() or out.returncode == 128:
        return True, "Tidak ada steam.exe yang jalan."
    return False, f"taskkill keluar dengan kode {out.returncode}: {out.stderr.strip()}"
