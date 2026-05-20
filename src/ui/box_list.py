"""Daftar box di area kanan: satu baris per akun, dengan status berwarna."""
import customtkinter as ctk

from src.monitor import BoxState

_STATE_COLOR = {
    BoxState.LAUNCHING: "#7a7a7a",
    BoxState.HEALTHY: "#3fb950",
    BoxState.ACCOUNT_PICKER: "#d6a532",
    BoxState.LOGIN_FORM: "#d6a532",
    BoxState.WAITING_2FA: "#d6a532",
    BoxState.STUCK_RETRY: "#3a8fd0",
    BoxState.STUCK_SPLASH: "#e5534b",
    BoxState.UNKNOWN: "#e5534b",
}


class BoxRow(ctk.CTkFrame):
    """Satu baris akun. Klik baris untuk memilih; tombol hapus menghapus box baris ini."""

    def __init__(self, master, username, box_name, on_select, on_delete, on_edit):
        super().__init__(master, fg_color="#242424")
        self.username = username
        self.selected = False
        self._on_select = on_select

        # Checkbox di paling kiri — menandai akun yang ikut "Run Tercentang".
        # Default tercentang; user bisa uncheck akun yang mau dilewati.
        self.checked = ctk.BooleanVar(value=True)
        self.check_btn = ctk.CTkCheckBox(self, text="", width=24,
                                         variable=self.checked)
        self.check_btn.pack(side="left", padx=(10, 0), pady=8)

        self.dot = ctk.CTkLabel(self, text="●", width=20, text_color="#7a7a7a")
        self.dot.pack(side="left", padx=(6, 6), pady=8)
        self.name_lbl = ctk.CTkLabel(self, text=username, font=("Segoe UI", 12, "bold"))
        self.name_lbl.pack(side="left")
        self.box_lbl = ctk.CTkLabel(self, text=f"  {box_name}", font=("Segoe UI", 10),
                                    text_color="#9a9a9a")
        self.box_lbl.pack(side="left")

        # tombol hapus per-baris -- TIDAK ikut memicu pemilihan baris
        self.del_btn = ctk.CTkButton(self, text="\U0001f5d1", width=32, fg_color="#5a2a28",
                                     hover_color="#743532",
                                     command=lambda: on_delete(self.username))
        self.del_btn.pack(side="right", padx=(4, 10))
        # tombol edit credential
        self.edit_btn = ctk.CTkButton(self, text="✏️", width=32,
                                      fg_color="#444444", hover_color="#555555",
                                      command=lambda: on_edit(self.username))
        self.edit_btn.pack(side="right", padx=(4, 0))
        self.badge = ctk.CTkLabel(self, text="-", font=("Segoe UI", 11),
                                  text_color="#9a9a9a")
        self.badge.pack(side="right", padx=4)

        # hanya widget non-tombol yang memicu pemilihan baris saat diklik
        for w in (self, self.dot, self.name_lbl, self.box_lbl, self.badge):
            w.bind("<Button-1>", lambda e: self._on_select(self.username))

    def is_checked(self) -> bool:
        return bool(self.checked.get())

    def set_checked(self, value: bool) -> None:
        self.checked.set(bool(value))

    def set_state(self, state: BoxState):
        color = _STATE_COLOR.get(state, "#7a7a7a")
        self.dot.configure(text_color=color)
        self.badge.configure(text=state.value, text_color=color)

    def set_selected(self, selected: bool):
        self.selected = selected
        self.configure(fg_color="#2f4a63" if selected else "#242424")


class BoxList(ctk.CTkScrollableFrame):
    """Kumpulan BoxRow. Menyediakan akses ke akun terpilih.

    `on_delete` adalah callback(username) yang dipanggil oleh tombol hapus tiap baris.
    `on_edit` adalah callback(username) yang dipanggil oleh tombol edit tiap baris.
    """

    def __init__(self, master, box_prefix, on_delete, on_edit):
        super().__init__(master, label_text="Akun / Status Box")
        self.box_prefix = box_prefix
        self._on_delete = on_delete
        self._on_edit = on_edit
        self.rows: dict[str, BoxRow] = {}
        self.selected: str | None = None

    def set_accounts(self, usernames: list[str]):
        for row in self.rows.values():
            row.destroy()
        self.rows.clear()
        self.selected = None
        for username in usernames:
            row = BoxRow(self, username, self.box_prefix + username,
                         self._select, self._on_delete, self._on_edit)
            row.pack(fill="x", pady=3, padx=2)
            self.rows[username] = row

    def _select(self, username):
        for name, row in self.rows.items():
            row.set_selected(name == username)
        self.selected = username

    def update_status(self, username, state: BoxState):
        if username in self.rows:
            self.rows[username].set_state(state)

    def checked_usernames(self) -> list[str]:
        """Daftar username yang checkbox-nya tercentang, urut tampilan."""
        return [u for u, row in self.rows.items() if row.is_checked()]

    def set_all_checked(self, value: bool) -> None:
        """Centang/uncheck semua baris sekaligus."""
        for row in self.rows.values():
            row.set_checked(value)
