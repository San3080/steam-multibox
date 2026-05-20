"""Panel log di sidebar: textbox read-only + tombol Copy All."""
import customtkinter as ctk

_LEVEL_COLORS = {"info": "#d6d6d6", "ok": "#3fb950", "error": "#e5534b"}


class LogPanel(ctk.CTkFrame):
    """Menampilkan entri LogBus. Teks bisa diseleksi; Copy All menyalin semua."""

    def __init__(self, master, logbus):
        super().__init__(master)
        self.logbus = logbus

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(header, text="LOG", font=("Segoe UI", 11, "bold")).pack(side="left")
        ctk.CTkButton(header, text="Copy All", width=80, height=24,
                      command=self._copy_all).pack(side="right")

        self.textbox = ctk.CTkTextbox(self, font=("Consolas", 11), wrap="word")
        self.textbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.textbox.configure(state="disabled")
        for level, color in _LEVEL_COLORS.items():
            self.textbox.tag_config(level, foreground=color)

        logbus.add_listener(self._on_entry)

    def _on_entry(self, entry):
        """Dipanggil dari thread mana pun -> jadwalkan ke thread GUI."""
        self.after(0, self._append, entry)

    def _append(self, entry):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", entry.format() + "\n", entry.level)
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def _copy_all(self):
        self.clipboard_clear()
        self.clipboard_append(self.logbus.all_text())
