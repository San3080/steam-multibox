"""Dialog Pengaturan: path (dengan Browse + Auto Find) + angka, disimpan ke config.json."""
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

from src.config import save_config, validate_config
from src.detect import SANDBOXIE_TOOLS, detect_sandboxie_dir, detect_steam_exe
from src import discord_webhook


class SettingsDialog(ctk.CTkToplevel):
    """Modal pengaturan. Memanggil on_saved(config) setelah simpan sukses."""

    def __init__(self, master, config, config_path, on_saved):
        super().__init__(master)
        self.title("Pengaturan")
        self.geometry("680x520")
        self.config_obj = config
        self.config_path = config_path
        self.on_saved = on_saved
        self.grab_set()

        self._path_vars: dict[str, ctk.StringVar] = {}
        self._num_vars: dict[str, ctk.StringVar] = {}

        # Auto Find aktif untuk Sandboxie & Steam; accounts pakai Browse saja.
        self._add_path_row("Folder Sandboxie", "sandboxie_dir", folder=True,
                           auto_find=self._auto_find_sandboxie)
        self._add_path_row("Path steam.exe", "steam_exe", folder=False,
                           auto_find=self._auto_find_steam)
        self._add_path_row("File accounts.txt", "accounts_file", folder=False)

        for field in ("stagger_seconds", "max_retries", "retry_check_delay",
                       "splash_timeout"):
            self._add_num_row(field)

        # Discord webhook URL + tombol Test
        self._add_webhook_row()

        ctk.CTkButton(self, text="Simpan", command=self._save).pack(pady=14)

    # --- baris UI ---

    def _add_path_row(self, label, field, folder, auto_find=None):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=6)
        ctk.CTkLabel(row, text=label, width=140, anchor="w").pack(side="left")
        var = ctk.StringVar(value=getattr(self.config_obj, field))
        self._path_vars[field] = var
        ctk.CTkEntry(row, textvariable=var).pack(side="left", fill="x",
                                                 expand=True, padx=6)
        ctk.CTkButton(row, text="Browse...", width=80,
                      command=lambda: self._browse(var, folder)).pack(side="left")
        if auto_find:
            ctk.CTkButton(row, text="Auto Find", width=80, fg_color="#1f6aa5",
                          command=auto_find).pack(side="left", padx=(4, 0))

    def _add_num_row(self, field):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=4)
        ctk.CTkLabel(row, text=field, width=140, anchor="w").pack(side="left")
        var = ctk.StringVar(value=str(getattr(self.config_obj, field)))
        self._num_vars[field] = var
        ctk.CTkEntry(row, textvariable=var, width=80).pack(side="left", padx=6)

    def _add_webhook_row(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(row, text="Discord webhook", width=140, anchor="w"
                     ).pack(side="left")
        self._webhook_var = ctk.StringVar(
            value=getattr(self.config_obj, "discord_webhook_url", ""))
        ctk.CTkEntry(row, textvariable=self._webhook_var,
                     placeholder_text="https://discord.com/api/webhooks/..."
                     ).pack(side="left", fill="x", expand=True, padx=6)
        ctk.CTkButton(row, text="Test", width=70, fg_color="#1f6aa5",
                      command=self._test_webhook).pack(side="left")

    def _test_webhook(self):
        url = self._webhook_var.get().strip()
        if not url:
            messagebox.showerror("Discord", "Isi URL webhook dulu.")
            return
        ok, detail = discord_webhook.send_message_with_detail(
            url, "🔧 Test webhook dari Steam Multi-Box Launcher")
        if ok:
            messagebox.showinfo("Discord", "Pesan test terkirim.")
        else:
            messagebox.showerror(
                "Discord — gagal kirim",
                f"{detail}\n\nCek URL & koneksi. URL valid format:\n"
                "https://discord.com/api/webhooks/<id>/<token>")

    # --- aksi ---

    def _browse(self, var, folder):
        path = filedialog.askdirectory() if folder else filedialog.askopenfilename()
        if path:
            var.set(os.path.normpath(path))

    def _auto_find_sandboxie(self):
        """Pindai semua drive untuk folder instalasi Sandboxie."""
        found = detect_sandboxie_dir()
        if found:
            self._path_vars["sandboxie_dir"].set(found)
            messagebox.showinfo("Auto Find", f"Sandboxie ditemukan:\n{found}")
        else:
            messagebox.showwarning(
                "Auto Find",
                "Sandboxie tidak ditemukan otomatis. Klik Browse untuk pilih manual.")

    def _auto_find_steam(self):
        """Pindai semua drive untuk steam.exe."""
        found = detect_steam_exe()
        if found:
            self._path_vars["steam_exe"].set(found)
            messagebox.showinfo("Auto Find", f"steam.exe ditemukan:\n{found}")
        else:
            messagebox.showwarning(
                "Auto Find",
                "steam.exe tidak ditemukan otomatis. Klik Browse untuk pilih manual.")

    def _save(self):
        cfg = self.config_obj
        cfg.sandboxie_dir = self._path_vars["sandboxie_dir"].get().strip()
        cfg.steam_exe = self._path_vars["steam_exe"].get().strip()
        cfg.accounts_file = self._path_vars["accounts_file"].get().strip()
        cfg.discord_webhook_url = self._webhook_var.get().strip()

        # validasi path
        if cfg.sandboxie_dir and not all(
                os.path.isfile(os.path.join(cfg.sandboxie_dir, t))
                for t in SANDBOXIE_TOOLS):
            messagebox.showerror("Pengaturan",
                                 "Folder Sandboxie tidak memuat Start.exe & SbieIni.exe.")
            return
        if cfg.steam_exe and not os.path.isfile(cfg.steam_exe):
            messagebox.showerror("Pengaturan", "steam.exe tidak ditemukan.")
            return

        try:
            for field, var in self._num_vars.items():
                setattr(cfg, field, int(var.get()))
        except ValueError:
            messagebox.showerror("Pengaturan", "Nilai angka tidak valid.")
            return

        errors = validate_config(cfg)
        if errors:
            messagebox.showerror("Pengaturan", "\n".join(errors))
            return

        save_config(cfg, self.config_path)
        self.on_saved(cfg)
        self.destroy()
