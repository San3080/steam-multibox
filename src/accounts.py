"""Membaca accounts.txt dan menulis fail.txt."""
from dataclasses import dataclass
import os


@dataclass
class Account:
    username: str
    password: str
    line_no: int


def read_accounts(path: str) -> tuple[list[Account], list[str]]:
    """Baca file kredensial. Kembalikan (daftar akun valid, daftar pesan error)."""
    if not os.path.exists(path):
        return [], [f"File akun tidak ditemukan: {path}"]

    accounts: list[Account] = []
    errors: list[str] = []
    with open(path, encoding="utf-8") as f:
        for i, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # Pemisah username/password: koma ATAU pipe ("|"), yang muncul lebih dulu.
            sep_positions = [line.index(c) for c in (",", "|") if c in line]
            if not sep_positions:
                errors.append(
                    f"Baris {i}: format harus 'username,password' atau "
                    "'username|password'")
                continue
            sep = min(sep_positions)
            user = line[:sep].strip()
            pw = line[sep + 1:].strip()
            if not user or not pw:
                errors.append(f"Baris {i}: username atau password kosong")
                continue
            accounts.append(Account(user, pw, i))
    return accounts, errors


def update_credential(path: str, old_username: str, new_username: str,
                      new_password: str) -> bool:
    """Ganti baris akun yang username-nya `old_username` dengan kredensial baru.

    Mempertahankan komentar, baris kosong, dan urutan baris. Mengembalikan
    True kalau ada baris yang diganti. Pemisah baru selalu pakai `,` agar
    output deterministik.
    """
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    changed = False
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Cek username baris ini: pisahkan di koma ATAU pipe, yang muncul duluan
        sep_positions = [stripped.index(c) for c in (",", "|") if c in stripped]
        if not sep_positions:
            continue
        sep = min(sep_positions)
        user = stripped[:sep].strip()
        if user.lower() != old_username.lower():
            continue
        # Pertahankan indentasi & newline asli; baris baru selalu pakai koma.
        prefix = raw[:len(raw) - len(raw.lstrip())]
        # cari newline ending
        if raw.endswith("\r\n"):
            nl = "\r\n"
        elif raw.endswith("\n"):
            nl = "\n"
        else:
            nl = ""
        lines[i] = f"{prefix}{new_username},{new_password}{nl}"
        changed = True
        break
    if not changed:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    return True


def write_failures(path: str, failures: list[tuple[Account, str]]) -> None:
    """Tulis akun gagal ke fail.txt. Format: 'username,password  # alasan'.

    Folder induk dibuat otomatis bila belum ada — supaya `data/fail.txt`
    tetap bisa ditulis meskipun pengguna belum pernah membuat folder `data/`.
    """
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for acc, reason in failures:
            f.write(f"{acc.username},{acc.password}  # {reason}\n")
