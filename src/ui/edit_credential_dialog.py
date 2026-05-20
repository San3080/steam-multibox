"""Dialog edit credential untuk satu box.

Klik Save -> konfirmasi popup -> callback(new_username, new_password).
Pemanggil yang melakukan persistence & wipe & relaunch.
"""
from tkinter import messagebox

import customtkinter as ctk


class EditCredentialDialog(ctk.CTkToplevel):
    def __init__(self, master, current_username: str, current_password: str,
                 on_saved):
        super().__init__(master)
        self.title(f"Edit Credential — {current_username}")
        self.geometry("440x230")
        self.on_saved = on_saved
        self._current_username = current_username
        self.grab_set()

        info = ctk.CTkLabel(
            self,
            text="Ubah username/password untuk box ini. Saat disimpan, sesi\n"
                 "Steam di box akan di-wipe lalu login ulang dengan data baru.",
            justify="left", anchor="w")
        info.pack(fill="x", padx=14, pady=(14, 8))

        self.user_var = ctk.StringVar(value=current_username)
        self.pw_var = ctk.StringVar(value=current_password)

        ctk.CTkLabel(self, text="Username:", anchor="w").pack(fill="x", padx=14)
        ctk.CTkEntry(self, textvariable=self.user_var).pack(
            fill="x", padx=14, pady=(2, 8))

        ctk.CTkLabel(self, text="Password:", anchor="w").pack(fill="x", padx=14)
        ctk.CTkEntry(self, textvariable=self.pw_var, show="•").pack(
            fill="x", padx=14, pady=(2, 12))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkButton(btn_row, text="Save", command=self._save).pack(
            side="left", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Batal", fg_color="#444444",
                      hover_color="#555555",
                      command=self.destroy).pack(side="left")

    def _save(self):
        new_user = self.user_var.get().strip()
        new_pw = self.pw_var.get().strip()
        if not new_user or not new_pw:
            messagebox.showerror(
                "Data tidak lengkap",
                "Username dan password tidak boleh kosong.")
            return
        if not messagebox.askyesno(
                "Konfirmasi",
                f"Profile sandbox '{self._current_username}' akan di-clear "
                "lalu login ulang dengan credential baru. Lanjutkan?"):
            return
        try:
            self.on_saved(self._current_username, new_user, new_pw)
        finally:
            self.destroy()
