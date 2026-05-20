"""Buffer log terpusat, aman dipanggil dari thread mana pun."""
from dataclasses import dataclass
import threading
import time


@dataclass
class LogEntry:
    timestamp: str
    level: str       # "info" | "ok" | "error"
    username: str
    message: str

    def format(self) -> str:
        prefix = f"{self.username}  " if self.username else ""
        return f"{self.timestamp}  {prefix}{self.message}"


class LogBus:
    """Menyimpan entri log dan memberi tahu listener (mis. GUI) saat ada entri baru."""

    def __init__(self):
        self._entries: list[LogEntry] = []
        self._lock = threading.Lock()
        self._listeners: list = []

    def add_listener(self, callback) -> None:
        """Daftarkan callback(entry) yang dipanggil tiap kali ada entri baru."""
        self._listeners.append(callback)

    def log(self, message: str, username: str = "", level: str = "info") -> LogEntry:
        """Tambah entri log baru dan kembalikan entri tersebut."""
        entry = LogEntry(time.strftime("%H:%M:%S"), level, username, message)
        with self._lock:
            self._entries.append(entry)
        for callback in list(self._listeners):
            callback(entry)
        return entry

    def all_entries(self) -> list[LogEntry]:
        with self._lock:
            return list(self._entries)

    def all_text(self) -> str:
        """Seluruh log sebagai satu string (sumber untuk tombol Copy All)."""
        return "\n".join(e.format() for e in self.all_entries())
