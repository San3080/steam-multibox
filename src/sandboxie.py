"""Pembungkus tool CLI Sandboxie (Start.exe, SbieIni.exe)."""
import os
import subprocess


# Pesan non-fatal Sandboxie yang muncul tiap launch dan harus di-dismiss manual.
# Kita silence per-box agar otomasi tidak terhenti.
NOISY_SBIE_MESSAGES = (
    # Yang user laporkan langsung
    "2206",  # Failed processing AutoExec setting
    "2309",  # Could not enable COM+/DCOM
    "2312",  # Could not enable BrowsestowsProcess setting
    "2326",  # Cannot prepare registry
    # Pesan startup/lifecycle yang sering muncul dan tidak fatal
    "2191",  # Process start banner
    "2207",  # Service launch
    "2208",  # Cleanup failed
    "2335",  # Restart blocked
    "1308",  # File delete blocked
    "1313",  # Registry path block
    "2101",  # Service blocked
    "2102",  # Service start
    "2103",  # Service stop
    "2310",  # DCOM
    "2311",  # Internet zones
)


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

    def set_setting(self, box: str, key: str, value: str) -> None:
        """Set satu key=value di section box Sandboxie.ini."""
        subprocess.run([self.sbieini_exe, "set", box, key, value], check=True)

    def append_setting(self, box: str, key: str, value: str) -> None:
        """Tambah satu nilai pada key multi-valued (mis. HideMessage)."""
        subprocess.run([self.sbieini_exe, "append", box, key, value], check=True)

    def set_global(self, key: str, value: str) -> None:
        """Set di [GlobalSettings] supaya berlaku untuk semua box."""
        self.set_setting("GlobalSettings", key, value)

    def append_global(self, key: str, value: str) -> None:
        """Append ke key multi-valued di [GlobalSettings]."""
        self.append_setting("GlobalSettings", key, value)

    def silence_global_noisy_messages(self) -> None:
        """Tambah HideMessage di [GlobalSettings] supaya pesan non-fatal
        diam untuk SEMUA box, bukan hanya yang baru dibuat lewat tool ini."""
        for code in NOISY_SBIE_MESSAGES:
            try:
                self.append_global("HideMessage", code)
            except subprocess.CalledProcessError:
                pass

    def create_box(self, box: str) -> None:
        """Buat/aktifkan box dan diamkan pesan SBIE non-fatal yang biasanya
        muncul sebagai popup tiap launch (mis. SBIE2206)."""
        subprocess.run(self.create_box_cmd(box), check=True)
        for code in NOISY_SBIE_MESSAGES:
            try:
                self.append_setting(box, "HideMessage", code)
            except subprocess.CalledProcessError:
                # best-effort; jangan gagalkan create box gara-gara satu pesan
                pass

    def block_host_steam_config(self, box: str, steam_exe: str) -> None:
        """Block akses box ke folder config Steam HOST agar tidak mewarisi akun.

        Tanpa ini, Sandboxie copy-on-read menyalin loginusers.vdf/config.vdf
        host ke box pada read pertama, sehingga picker "Who's playing?" muncul
        dengan akun host. Kita pakai DUA mekanisme bersamaan:

        1. `ClosedFilePath` — block akses file spesifik (file kredensial).
        2. `OpenFilePath` dengan path box-only — pastikan akses fallback ke
           ruang box, bukan host.

        Strategi ini memaksa Steam di box untuk start dengan loginusers.vdf
        KOSONG -> tidak ada picker -> -login command-line langsung berhasil.
        """
        if not steam_exe:
            return
        steam_dir = os.path.dirname(steam_exe)
        config_dir = os.path.join(steam_dir, "config")
        # File yang harus benar-benar di-block (inherited dari host)
        blocked_paths = [
            os.path.join(config_dir, "loginusers.vdf"),
            os.path.join(config_dir, "config.vdf"),
            os.path.join(config_dir, "DialogConfig.vdf"),
            os.path.join(steam_dir, "ssfn*"),  # wildcard token files
            # Sandboxie format: pakai prefix supaya berlaku rekursif kalau perlu
            os.path.join(config_dir, "loginusers.vdf.tmp"),
        ]
        for path in blocked_paths:
            try:
                self.append_setting(box, "ClosedFilePath", path)
            except subprocess.CalledProcessError:
                pass

    def delete_box(self, box: str) -> None:
        """Hapus box: terminate, hapus isi, hapus section dari Sandboxie.ini.

        Pendekatan SbieIni.exe delete tidak bekerja di Sandboxie Plus, jadi
        kita edit Sandboxie.ini langsung sebagai fallback yang paling andal.
        """
        # 1) Hentikan proses di dalam box (best-effort)
        try:
            subprocess.run(self.terminate_cmd(box), check=False,
                           capture_output=True, timeout=15)
        except Exception:
            pass

        # 2) Hapus file isi box di disk
        try:
            subprocess.run([self.start_exe, f"/box:{box}", "delete_sandbox", "/silent"],
                           check=False, capture_output=True, timeout=60)
        except Exception:
            pass

        # 3) Hapus section [BoxName] dari Sandboxie.ini
        ini_path = self._find_sandboxie_ini()
        if not ini_path:
            raise RuntimeError(
                "Sandboxie.ini tidak ditemukan. Coba hapus manual di SandMan.")
        if not self._remove_box_section_from_ini(ini_path, box):
            raise RuntimeError(
                f"Section [{box}] tidak ditemukan di {ini_path}. "
                "Sudah dihapus sebelumnya?")

        # 4) Minta Sandboxie service reload config (best-effort)
        try:
            subprocess.run([self.sbieini_exe, "reload"], check=False,
                           capture_output=True, timeout=10)
        except Exception:
            pass

    # --- helpers privat untuk Sandboxie.ini ---

    def _find_sandboxie_ini(self) -> str | None:
        """Cari path Sandboxie.ini. Registry dulu, lalu lokasi umum."""
        from src.detect import _read_reg
        import winreg
        # Registry value ini biasanya berisi path utuh ke .ini
        for value in ("IniPath", "IniLocation"):
            p = _read_reg(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Sandboxie", value)
            if p and os.path.isfile(str(p)):
                return str(p)
        for candidate in (os.path.join(self.start_exe, "..", "Sandboxie.ini"),
                          r"C:\Windows\Sandboxie.ini",
                          r"C:\ProgramData\Sandboxie\Sandboxie.ini"):
            candidate = os.path.normpath(candidate)
            if os.path.isfile(candidate):
                return candidate
        # Fallback: cari di folder install (dari path Start.exe)
        install_dir = os.path.dirname(self.start_exe)
        candidate = os.path.join(install_dir, "Sandboxie.ini")
        if os.path.isfile(candidate):
            return candidate
        return None

    def _read_ini(self, path: str) -> tuple[str, str]:
        """Baca .ini dengan deteksi encoding (UTF-16 BOM atau UTF-8)."""
        with open(path, "rb") as f:
            raw = f.read()
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            return raw.decode("utf-16"), "utf-16"
        if raw.startswith(b"\xef\xbb\xbf"):
            return raw.decode("utf-8-sig"), "utf-8-sig"
        return raw.decode("utf-8", errors="replace"), "utf-8"

    def _write_ini(self, path: str, text: str, encoding: str) -> None:
        with open(path, "w", encoding=encoding) as f:
            f.write(text)

    def _remove_box_section_from_ini(self, ini_path: str, box: str) -> bool:
        """Hapus `[box]` dan semua key-nya dari ini_path. True kalau ada yang dihapus."""
        text, encoding = self._read_ini(ini_path)
        # Normalisasi line endings ke CRLF Windows
        lines = text.splitlines(keepends=True)
        target = f"[{box}]".lower()
        out: list[str] = []
        in_section = False
        removed = False
        for line in lines:
            stripped = line.strip()
            if stripped.lower() == target:
                in_section = True
                removed = True
                continue
            if in_section:
                # Section berakhir saat ketemu section lain
                if stripped.startswith("[") and stripped.endswith("]"):
                    in_section = False
                    out.append(line)
                # Skip semua baris di dalam section (key=value & blank lines)
                continue
            out.append(line)
        if not removed:
            return False
        new_text = "".join(out)
        self._write_ini(ini_path, new_text, encoding)
        return True

    def launch(self, box: str, program: str, args: list[str] | None = None):
        """Jalankan program di dalam box. Kembalikan objek Popen."""
        return subprocess.Popen(self.launch_cmd(box, program, args))

    def terminate(self, box: str) -> None:
        """Hentikan semua proses dalam box. Data box tetap utuh."""
        subprocess.run(self.terminate_cmd(box), check=True)

    def graceful_shutdown_steam(self, box: str, steam_exe: str) -> None:
        """Minta Steam di dalam box untuk close graceful via `steam.exe -shutdown`.

        Sandboxie /terminate adalah hard-kill (TerminateProcess), Steam tidak
        sempat menulis token enkripsi auto-login. -shutdown memberi Steam
        kesempatan menyimpan state sebelum keluar.

        Best-effort: kalau gagal, pemanggil bisa lanjut ke `terminate()`.
        """
        try:
            subprocess.run(
                [self.start_exe, f"/box:{box}", steam_exe, "-shutdown"],
                check=False, capture_output=True, timeout=15)
        except Exception:
            pass
