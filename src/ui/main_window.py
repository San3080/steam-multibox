"""Jendela utama (Layout A): sidebar aksi + log, area kanan daftar box."""
import os
from tkinter import messagebox

import customtkinter as ctk

from src.accounts import read_accounts, update_credential
from src import discord_webhook
from src.config import save_config
from src.controller import Controller, SteamBoxDriver
from src.detect import detect_sandboxie_dir, detect_steam_exe
from src.host_steam import is_host_steam_running, kill_host_steam
from src.login_verify import find_box_root, wipe_steam_session
from src.sandman import open_sandboxie_ui
from src.ui.box_list import BoxList
from src.ui.edit_credential_dialog import EditCredentialDialog
from src.ui.log_panel import LogPanel
from src.ui.settings_dialog import SettingsDialog


class MainWindow(ctk.CTk):
    def __init__(self, config, config_path, logbus):
        super().__init__()
        self.config_obj = config
        self.config_path = config_path
        self.logbus = logbus
        self._controller: Controller | None = None
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
        ctk.CTkButton(actions, text="▶  Run Tercentang",
                      command=self._on_run_checked).pack(fill="x", pady=4)

        # Tombol kecil centang semua / hapus centang
        check_row = ctk.CTkFrame(actions, fg_color="transparent")
        check_row.pack(fill="x", pady=(0, 4))
        ctk.CTkButton(check_row, text="Centang semua", fg_color="#333333",
                      hover_color="#444444", height=24,
                      command=lambda: self.box_list.set_all_checked(True)
                      ).pack(side="left", fill="x", expand=True, padx=(0, 2))
        ctk.CTkButton(check_row, text="Hapus centang", fg_color="#333333",
                      hover_color="#444444", height=24,
                      command=lambda: self.box_list.set_all_checked(False)
                      ).pack(side="left", fill="x", expand=True, padx=(2, 0))

        ctk.CTkButton(actions, text="■  Stop / Terminate", fg_color="#333333",
                      command=self._on_stop).pack(fill="x", pady=4)
        ctk.CTkButton(actions, text="Tutup Steam Host", fg_color="#7a3a1c",
                      hover_color="#9a4a2c",
                      command=self._on_kill_host).pack(fill="x", pady=4)
        ctk.CTkButton(actions, text="Buka Sandboxie UI", fg_color="#444444",
                      hover_color="#555555",
                      command=self._on_open_ui).pack(fill="x", pady=4)
        ctk.CTkButton(actions, text="Hapus Box Terpilih", fg_color="#5a2a28",
                      command=self._on_delete).pack(fill="x", pady=4)
        ctk.CTkButton(actions, text="Reset Semua Box", fg_color="#5a2a28",
                      hover_color="#743532",
                      command=self._on_reset_all).pack(fill="x", pady=4)

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
        self.box_list = BoxList(main, self.config_obj.box_prefix,
                                self._delete_box, self._on_edit_credential)
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
            return
        # Diamkan pesan non-fatal Sandboxie secara global agar tidak nge-blok
        # box-box berikutnya kalau popup "Messages from Sandboxie" muncul.
        try:
            SteamBoxDriver(self.config_obj, logbus=self.logbus
                           ).sandboxie.silence_global_noisy_messages()
            self.logbus.log("Sandboxie: pesan non-fatal di-silence global.",
                            "", "info")
        except Exception as e:
            self.logbus.log(f"gagal silence pesan Sandboxie: {e}", "", "error")

    def _reload_accounts(self):
        # Migrasi otomatis: kalau accounts_file lama ("accounts.txt") tidak ada
        # padahal data/accounts.txt tersedia, pindahkan rujukan ke folder baru
        # supaya user tidak perlu setting ulang setelah upgrade.
        if (not os.path.isfile(self.config_obj.accounts_file)
                and os.path.isfile("data/accounts.txt")):
            self.logbus.log(
                f"accounts_file '{self.config_obj.accounts_file}' tidak ada, "
                "dialihkan ke 'data/accounts.txt'.", "", "ok")
            self.config_obj.accounts_file = "data/accounts.txt"
            save_config(self.config_obj, self.config_path)

        # Migrasi: 'ui' dan 'cmdline' tidak men-save ssfn token yang dibutuhkan
        # untuk auto-login saat reopen manual. 'keyboard' (default baru) kirim
        # keystroke ke form login dengan Remember me dicentang -> Steam menulis
        # ssfn + encrypted token, sehingga reopen box langsung auto-login.
        if self.config_obj.login_method in ("ui", "cmdline"):
            old = self.config_obj.login_method
            self.logbus.log(
                f"login_method '{old}' dialihkan ke 'keyboard' "
                "(auto-centang Remember me; auto-save ssfn token).",
                "", "info")
            self.config_obj.login_method = "keyboard"
            save_config(self.config_obj, self.config_path)

        accounts, errors = read_accounts(self.config_obj.accounts_file)
        for err in errors:
            self.logbus.log(err, "", "error")
        self._accounts = accounts
        self.box_list.set_accounts([a.username for a in accounts])
        if accounts:
            self.logbus.log(f"{len(accounts)} akun dimuat dari "
                            f"{self.config_obj.accounts_file}", "", "ok")
        else:
            self.logbus.log(
                f"tidak ada akun yang dimuat dari "
                f"{self.config_obj.accounts_file} — isi file ini lalu klik "
                "Pengaturan untuk reload.", "", "error")

    def _make_controller(self) -> Controller:
        driver = SteamBoxDriver(self.config_obj, logbus=self.logbus)
        fail_path = os.path.join(
            os.path.dirname(os.path.abspath(self.config_obj.accounts_file)) or ".",
            "fail.txt")
        self._controller = Controller(self.config_obj, self.logbus, driver,
                                      fail_path=fail_path,
                                      status_cb=self._on_status)
        return self._controller

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
        if not self._accounts:
            self.logbus.log(
                f"tidak ada akun di {self.config_obj.accounts_file} — Create "
                "dilewati.", "", "error")
            messagebox.showinfo(
                "Tidak ada akun",
                f"File {self.config_obj.accounts_file} kosong atau tidak ada. "
                "Isi 'username,password' tiap baris, lalu coba lagi.")
            return
        self.logbus.log(f"Create Boxes untuk {len(self._accounts)} akun…", "", "ok")
        driver = SteamBoxDriver(self.config_obj, logbus=self.logbus)
        for acc in self._accounts:
            box = self.config_obj.box_prefix + acc.username
            try:
                driver.ensure_box(box)
                self.logbus.log("box siap", acc.username, "ok")
            except Exception as e:
                self.logbus.log(f"gagal buat box: {e}", acc.username, "error")
        self.logbus.log("Create Boxes selesai.", "", "ok")
        ok, msg = open_sandboxie_ui(self.config_obj.sandboxie_dir)
        self.logbus.log(msg, "", "ok" if ok else "info")

    def _on_run(self):
        """Run semua akun yang dimuat dari accounts.txt."""
        self._run_accounts(self._accounts, label="Run Semua")

    def _on_run_checked(self):
        """Run hanya akun yang checkbox-nya tercentang di daftar box."""
        checked = set(self.box_list.checked_usernames())
        subset = [a for a in self._accounts if a.username in checked]
        if not subset:
            self.logbus.log("Tidak ada akun tercentang — Run Tercentang dilewati.",
                            "", "error")
            messagebox.showinfo(
                "Tidak ada centang",
                "Centang dulu minimal satu akun di daftar, lalu coba lagi.")
            return
        skipped = len(self._accounts) - len(subset)
        if skipped:
            self.logbus.log(f"{skipped} akun tidak dicentang → dilewati.",
                            "", "info")
        self._run_accounts(subset, label="Run Tercentang")

    def _run_accounts(self, accounts, label):
        """Logika bersama Run Semua & Run Tercentang."""
        if not self._paths_ok():
            return
        if not accounts:
            self.logbus.log(
                f"tidak ada akun untuk {label} — dilewati.", "", "error")
            messagebox.showinfo(
                "Tidak ada akun",
                f"File {self.config_obj.accounts_file} kosong atau tidak ada. "
                "Isi 'username,password' tiap baris, lalu coba lagi.")
            return
        if is_host_steam_running():
            if not messagebox.askyesno(
                    "Steam host terdeteksi",
                    "Ada steam.exe sedang berjalan. Steam single-instance: "
                    "kalau host jalan, Steam di sandbox akan diteruskan ke host "
                    "(bukan login ke akun box).\n\n"
                    "Tutup Steam host sekarang dan lanjutkan Run?"):
                self.logbus.log("Run dibatalkan: Steam host belum ditutup.",
                                "", "error")
                return
            ok, msg = kill_host_steam()
            self.logbus.log(msg, "", "ok" if ok else "error")
            if not ok:
                return
        self.logbus.log(f"{label}: memproses {len(accounts)} akun bergiliran…",
                        "", "ok")
        # Notif Discord: run mulai
        discord_webhook.notify_run_start(
            self.config_obj.discord_webhook_url, label, len(accounts))
        self._make_controller().run_async(accounts)

    def _on_stop(self):
        if not self.config_obj.sandboxie_dir:
            return
        if self._controller is not None:
            self._controller.request_stop()
            self.logbus.log("Stop diminta — controller akan berhenti setelah "
                            "polling berikutnya.", "", "ok")
        driver = SteamBoxDriver(self.config_obj, logbus=self.logbus)
        for acc in self._accounts:
            box = self.config_obj.box_prefix + acc.username
            try:
                driver.terminate(box)
            except Exception as e:
                self.logbus.log(f"gagal terminate box: {e}",
                                acc.username, "error")
        self.logbus.log("semua box di-terminate.", "", "ok")

    def _on_kill_host(self):
        ok, msg = kill_host_steam()
        self.logbus.log(msg, "", "ok" if ok else "error")

    def _on_open_ui(self):
        ok, msg = open_sandboxie_ui(self.config_obj.sandboxie_dir)
        self.logbus.log(msg, "", "ok" if ok else "error")

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
            SteamBoxDriver(self.config_obj, logbus=self.logbus).sandboxie.delete_box(box)
            self.logbus.log(f"box {box} dihapus.", username, "ok")
        except Exception as e:
            self.logbus.log(f"gagal hapus box: {e}", username, "error")

    def _on_reset_all(self):
        """Hapus SEMUA box (per accounts.txt) sekaligus. Dipakai setelah update
        besar yang mengubah cara box dibuat (mis. ClosedFilePath baru) supaya
        box dibuat ulang fresh tanpa state warisan."""
        if not self.config_obj.sandboxie_dir:
            messagebox.showerror("Reset Semua", "Folder Sandboxie belum di-set.")
            return
        if not self._accounts:
            messagebox.showinfo("Reset Semua", "Tidak ada akun di accounts.txt.")
            return
        if not messagebox.askyesno(
                "Reset Semua Box",
                f"Hapus {len(self._accounts)} box ({self.config_obj.box_prefix}*) "
                "beserta SEMUA datanya?\n\n"
                "Setelah ini kamu perlu Run lagi untuk membuat box baru."):
            return
        driver = SteamBoxDriver(self.config_obj, logbus=self.logbus)
        success = 0
        failed = 0
        for acc in self._accounts:
            box = self.config_obj.box_prefix + acc.username
            try:
                driver.sandboxie.delete_box(box)
                self.logbus.log(f"box {box} dihapus.", acc.username, "ok")
                success += 1
            except Exception as e:
                self.logbus.log(f"gagal hapus: {e}", acc.username, "error")
                failed += 1
        self.logbus.log(
            f"Reset Semua Box selesai: {success} dihapus, {failed} gagal.",
            "", "ok")

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

    # --- edit credential per-box ---

    def _on_edit_credential(self, username: str):
        """Buka dialog edit credential untuk box `username`."""
        acc = next((a for a in self._accounts if a.username == username), None)
        if acc is None:
            messagebox.showerror("Edit", f"Akun {username} tidak ditemukan.")
            return
        EditCredentialDialog(self, acc.username, acc.password,
                             self._apply_credential_change)

    def _apply_credential_change(self, old_username: str, new_username: str,
                                  new_password: str):
        """Persist credential baru, wipe (atau delete) box lama, lalu run akun baru."""
        username_changed = old_username.lower() != new_username.lower()
        old_box = self.config_obj.box_prefix + old_username

        # 1) Kalau username berubah, hapus box lama dulu (biar tidak nyangkut di
        #    Sandboxie tanpa entri di accounts.txt). Konfirmasi user dulu.
        if username_changed:
            if not messagebox.askyesno(
                    "Hapus box lama?",
                    f"Username berubah dari '{old_username}' ke '{new_username}'.\n\n"
                    f"Box lama '{old_box}' tidak akan dipakai lagi oleh tool ini. "
                    "Hapus box lama beserta datanya sekarang?"):
                self.logbus.log(
                    f"box lama '{old_box}' dibiarkan; hapus manual di SandMan "
                    "kalau perlu.", "", "info")
            else:
                try:
                    SteamBoxDriver(
                        self.config_obj, logbus=self.logbus
                    ).sandboxie.delete_box(old_box)
                    self.logbus.log(f"box {old_box} dihapus.", old_username, "ok")
                except Exception as e:
                    self.logbus.log(f"gagal hapus box lama: {e}",
                                    old_username, "error")

        # 2) Tulis credential baru ke accounts.txt
        if not update_credential(self.config_obj.accounts_file,
                                 old_username, new_username, new_password):
            self.logbus.log(
                f"gagal update {self.config_obj.accounts_file} untuk {old_username}",
                "", "error")
            return
        self.logbus.log(
            f"credential {old_username} -> {new_username} disimpan ke "
            f"{self.config_obj.accounts_file}", "", "ok")

        # 3) Wipe sesi Steam di box lama (kalau username sama → box lama = box baru;
        #    kalau username berubah dan box lama sudah ke-delete di langkah 1, ini
        #    akan no-op dengan aman karena find_box_root mengembalikan None)
        if not username_changed:
            root = find_box_root(old_box)
            if root:
                n, _ = wipe_steam_session(root)
                self.logbus.log(
                    f"wipe sesi Steam box {old_box}: {n} file dihapus", "", "ok")

        # 4) Reload daftar akun (kalau username berubah, baris box list ikut update)
        self._reload_accounts()

        # 5) Jalankan akun baru sendirian via controller (UI form + Remember me)
        if not self._paths_ok():
            return
        new_acc = next((a for a in self._accounts
                        if a.username == new_username), None)
        if new_acc is None:
            self.logbus.log(
                f"akun {new_username} tidak ditemukan setelah update", "", "error")
            return
        self.logbus.log(
            f"Run akun {new_username} (sendirian) untuk login ulang…", "", "ok")
        # Notif Discord: ada edit credential (audit trail).
        discord_webhook.notify_edit(
            self.config_obj.discord_webhook_url,
            old_username, new_username, password_changed=True)
        self._make_controller().run_async([new_acc])
