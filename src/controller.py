"""Orkestrasi Run bergiliran + driver IO nyata + threading untuk GUI."""
import queue
import threading
import time

from src.accounts import write_failures
from src import discord_webhook
from src.login_verify import (verify_login, find_box_root, wipe_steam_session,
                              enable_remember_password, prime_clean_steam_config)
from src.monitor import BoxState, classify
from src.sandboxie import Sandboxie
from src.steam import build_login_args
from src import steam_ui

# batas polling agar tidak menunggu selamanya untuk satu percobaan
_MAX_POLLS_PER_ATTEMPT = 12


class _NullLog:
    def log(self, *a, **k):
        pass


class SteamBoxDriver:
    """Driver IO nyata: menggerakkan Sandboxie + Steam + otomasi jendela."""

    def __init__(self, config, logbus=None):
        self.config = config
        self.sandboxie = Sandboxie(config.sandboxie_dir)
        self.log = logbus or _NullLog()

    def ensure_box(self, box):
        self.sandboxie.create_box(box)
        # Cegah Sandboxie copy-on-read file Steam config dari host (mencegah
        # akun host bocor ke box yang membuat picker "Who's playing?" muncul).
        self.sandboxie.block_host_steam_config(box, self.config.steam_exe)

    def launch(self, account, box):
        """Launch Steam di box.

        - login_method='cmdline': `steam.exe -login user pass` (fast, no token save)
        - login_method='ui' (default): launch polos; tool akan UI-fill form dengan
          Remember me dicentang -> Steam simpan encrypted token untuk auto-login.
        """
        if self.config.login_method == "ui":
            self.sandboxie.launch(box, self.config.steam_exe)
        else:
            args = build_login_args(self.config.steam_exe,
                                    account.username, account.password)
            self.sandboxie.launch(box, args[0], args[1:])

    def terminate(self, box):
        self.sandboxie.terminate(box)

    def graceful_shutdown(self, box):
        """Tutup Steam di box graceful sebelum hard-terminate.

        Penting: hard-terminate (TerminateProcess) tidak memberi Steam waktu
        menulis token enkripsi auto-login. Sehabis ini, panggil `terminate`
        untuk membersihkan proses sisa setelah jeda.
        """
        self.sandboxie.graceful_shutdown_steam(box, self.config.steam_exe)

    def click_add(self) -> bool:
        return bool(steam_ui.click_add_account())

    def fill_login(self, account) -> bool:
        return bool(steam_ui.fill_login_form(account.username, account.password))

    def poll(self, box, elapsed, expected_username=None):
        snap = steam_ui.snapshot_box(
            box, elapsed,
            debug_log=lambda m: self.log.log(m, "", "info"),
            expected_username=expected_username)
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
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def request_stop(self):
        """Minta controller berhenti secepatnya. Aman dipanggil dari thread lain."""
        self._stop_event.set()

    def _wait(self, seconds: float) -> bool:
        """Tunggu `seconds` detik atau sampai stop diminta. True jika stop diminta.

        Memakai stop_event.wait yang sebenarnya bisa diinterrupt. Pada tes,
        stop_event tidak diset sehingga akan menunggu — karena itu tes selalu
        memakai `seconds=0` via config dengan delay 0.
        """
        if seconds <= 0:
            return self._stop_event.is_set()
        return self._stop_event.wait(timeout=seconds)

    # --- pemrosesan satu akun ---

    def process_account(self, account) -> tuple[bool, str]:
        box = self.config.box_prefix + account.username
        self._set_status(account.username, BoxState.LAUNCHING)
        if self._stop_event.is_set():
            return False, "dihentikan"
        try:
            self.driver.ensure_box(box)
        except Exception as e:
            self.log.log(f"gagal membuat box: {e}", account.username, "error")
            return False, f"box gagal dibuat: {e}"

        attempts = self.config.max_retries + 1
        for attempt in range(1, attempts + 1):
            if self._stop_event.is_set():
                return False, "dihentikan"
            # Bersihkan state inherited (loginusers.vdf, config.vdf, ssfn*) supaya
            # box mulai dari kondisi nol. Steam akan tulis ulang setelah login.
            root = find_box_root(box)
            if root:
                removed = prime_clean_steam_config(root)
                if removed:
                    self.log.log(f"clean state Steam: {removed} file dihapus",
                                 account.username, "info")
            try:
                self.driver.launch(account, box)
            except Exception as e:
                self.log.log(f"gagal launch: {e}", account.username, "error")
                return False, f"launch gagal: {e}"

            outcome, reason = self._await_login(account, box)
            if outcome == "ok":
                verdict = self._check_login_match(account, box)
                if verdict == "mismatch":
                    self.log.log(
                        f"akun salah -- wipe sesi & retry "
                        f"({attempt}/{attempts})",
                        account.username, "error")
                    self._safe_terminate(box)
                    self._wipe_session(box)
                    continue
                # match atau unknown -> anggap sukses
                self.log.log("login berhasil", account.username, "ok")
                return True, ""
            if outcome == "fail":
                self.log.log(f"box di-terminate (alasan: {reason})",
                             account.username, "error")
                self._safe_terminate(box)
                return False, reason
            if outcome == "stopped":
                self._safe_terminate(box)
                return False, "dihentikan"
            # stuck
            self.log.log(f"box di-terminate (alasan: {reason or 'stuck'}); "
                         f"retry {attempt}/{attempts}",
                         account.username, "error")
            self._safe_terminate(box)

        return False, f"login terus ke akun salah atau stuck setelah {self.config.max_retries} retry"

    def _await_login(self, account, box) -> tuple[str, str]:
        """Pantau satu percobaan. Kembalikan (outcome, reason).

        outcome: 'ok' | 'stuck' | 'fail' | 'stopped'
        """
        if self._wait(self.config.retry_check_delay):
            return "stopped", ""
        filled = False           # form login hanya boleh diisi SEKALI per attempt
        picker_clicked = False   # tombol + cukup diklik sekali
        # Lacak elapsed nyata sejak launch agar snapshot bisa pakai heuristik
        # "Steam sudah lama jalan tanpa error → probably healthy".
        elapsed = float(self.config.retry_check_delay)
        for _ in range(_MAX_POLLS_PER_ATTEMPT):
            if self._stop_event.is_set():
                return "stopped", ""
            state = self.driver.poll(box, elapsed,
                                     expected_username=account.username)
            self._set_status(account.username, state)

            if state == BoxState.HEALTHY:
                return "ok", ""
            if state == BoxState.LOGIN_FAILED:
                return "fail", "Steam menolak login (password/username salah, atau rate-limit)"
            if state in (BoxState.STUCK_RETRY, BoxState.STUCK_SPLASH):
                return "stuck", state.value
            if state == BoxState.ACCOUNT_PICKER and not picker_clicked:
                if self.driver.click_add():
                    picker_clicked = True
                # gagal klik + → biarkan, akan dicoba di poll berikutnya
            elif state == BoxState.LOGIN_FORM and not filled:
                if self.driver.fill_login(account):
                    filled = True
                else:
                    # Jendela "Sign in to Steam" tapi TIDAK ada Edit field —
                    # kemungkinan ini sebenarnya account picker (title-nya sama
                    # di Sandboxie Plus). Coba klik "+" agar masuk ke form login.
                    self.log.log("form login terdeteksi tapi field tidak "
                                 "ada; mungkin picker — klik '+'",
                                 account.username, "info")
                    if self.driver.click_add():
                        picker_clicked = True
            # WAITING_2FA / LAUNCHING / UNKNOWN -> just keep watching
            if self._wait(self.config.poll_interval):
                return "stopped", ""
            elapsed += float(self.config.poll_interval)
        return "stuck", "polling habis tanpa keadaan terminal"

    def _check_login_match(self, account, box) -> str:
        """Verifikasi akun yang login. Kembalikan 'match' | 'mismatch' | 'unknown'.

        Selalu log hasilnya.
        """
        matched, detail = verify_login(box, account.username)
        if matched is True:
            self.log.log(detail, account.username, "ok")
            # Set RememberPassword=1 supaya buka manual lewat Sandboxie nanti
            # otomatis login (tanpa minta credential lagi).
            root = find_box_root(box)
            if root and enable_remember_password(root):
                self.log.log("RememberPassword=1 disetel untuk auto-login berikutnya",
                             account.username, "ok")
            return "match"
        if matched is False:
            self.log.log(f"PERINGATAN: {detail}", account.username, "error")
            return "mismatch"
        # matched is None
        return "unknown"

    def _wipe_session(self, box):
        root = find_box_root(box)
        if not root:
            self.log.log("tidak bisa wipe sesi Steam: folder box tidak ditemukan",
                         "", "error")
            return
        n, _removed = wipe_steam_session(root)
        if n:
            self.log.log(f"wipe sesi Steam: {n} file dihapus", "", "ok")
        else:
            self.log.log("wipe sesi Steam: tidak ada file untuk dihapus", "", "info")

    def _safe_terminate(self, box):
        try:
            self.driver.terminate(box)
        except Exception as e:
            self.log.log(f"gagal terminate box: {e}", "", "error")

    def _graceful_then_terminate(self, box, username):
        """Tutup Steam graceful (kasih waktu save state) lalu hard-terminate."""
        try:
            self.driver.graceful_shutdown(box)
            self.log.log(
                f"shutdown graceful Steam (menunggu {self.config.terminate_grace_seconds}s "
                "untuk save state)…", username, "info")
        except Exception as e:
            self.log.log(f"graceful shutdown gagal, lanjut hard-terminate: {e}",
                         username, "info")
        # Tunggu Steam selesai save state — bisa diinterupsi oleh stop_event.
        self._wait(self.config.terminate_grace_seconds)
        self._safe_terminate(box)
        self.log.log("auto-terminate setelah sukses", username)

    # --- menjalankan semua akun (bergiliran) ---

    def run_sync(self, accounts) -> tuple[int, int]:
        """Proses semua akun berurutan. Kembalikan (jumlah_sukses, jumlah_gagal)."""
        if len(accounts) > 6:
            self.log.log(f"PERINGATAN: {len(accounts)} akun -- butuh RAM/CPU besar "
                         f"untuk klien Steam sebanyak itu.", "", "error")
        failures = []
        success = 0
        for account in accounts:
            if self._stop_event.is_set():
                self.log.log(f"Run dihentikan sebelum {account.username}", "", "error")
                break
            ok, reason = self.process_account(account)
            # Notif Discord per-akun (best-effort, tidak ganggu run kalau gagal).
            discord_webhook.notify_login(
                self.config.discord_webhook_url, account.username, ok, reason)
            if ok:
                success += 1
                if self.config.auto_terminate_on_success:
                    box = self.config.box_prefix + account.username
                    # Graceful shutdown dulu — kasih Steam waktu menulis token
                    # enkripsi & state ke disk supaya buka manual nanti auto-login.
                    self._graceful_then_terminate(box, account.username)
            else:
                failures.append((account, reason))
            if self._stop_event.is_set():
                break
            self._wait(self.config.stagger_seconds)

        write_failures(self.fail_path, failures)
        self.log.log(f"selesai: {success} sukses, {len(failures)} gagal.", "", "ok")
        if failures:
            self.log.log(f"akun gagal dicatat di {self.fail_path}", "", "error")
        # Notif Discord ringkasan akhir.
        discord_webhook.notify_run_done(
            self.config.discord_webhook_url, success, len(failures),
            failures=[(a.username, r) for a, r in failures])
        return success, len(failures)

    def run_async(self, accounts) -> None:
        """Jalankan run_sync di thread latar belakang (dipakai GUI)."""
        self._thread = threading.Thread(target=self.run_sync, args=(accounts,),
                                        daemon=True)
        self._thread.start()

    def _set_status(self, username, state: BoxState):
        self.updates.put((username, state))
        self.status_cb(username, state)
