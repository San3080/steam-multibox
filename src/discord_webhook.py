"""Notifikasi Discord webhook untuk event run/login/edit.

Best-effort: kegagalan jaringan tidak boleh mengganggu run di tool. Semua
fungsi tidak pernah melempar ke pemanggil.
"""
import json
import urllib.error
import urllib.request

# Discord menolak content lebih dari 2000 karakter
_MAX_CONTENT = 1900


def _post(webhook_url: str, payload: dict, timeout: float = 5.0) -> tuple[bool, str]:
    """Kirim payload JSON ke webhook. Return (ok, detail).

    detail:
      - "" saat sukses
      - alasan kegagalan (kode HTTP + body, atau pesan eksepsi) saat gagal
    """
    if not webhook_url or not webhook_url.strip():
        return False, "URL webhook kosong"
    url = webhook_url.strip()
    if not url.lower().startswith(("http://", "https://")):
        return False, f"URL harus diawali http(s)://, dapat: {url[:60]}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json",
                 "User-Agent": "SteamMultiBox/1.0"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if 200 <= resp.status < 300:
                return True, ""
            body = resp.read(500).decode("utf-8", errors="replace")
            return False, f"HTTP {resp.status}: {body[:200]}"
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(500).decode("utf-8", errors="replace")
        except Exception:
            pass
        return False, f"HTTP {e.code}: {body[:200] or e.reason}"
    except urllib.error.URLError as e:
        return False, f"Tidak bisa connect: {e.reason}"
    except (TimeoutError, OSError) as e:
        return False, f"Network error: {e}"


def send_message(webhook_url: str, content: str,
                 username: str = "Steam Multi-Box") -> bool:
    """Kirim pesan teks. Content otomatis dipotong agar muat batas Discord."""
    if not webhook_url:
        return False
    body = content[:_MAX_CONTENT]
    ok, _ = _post(webhook_url, {"content": body, "username": username})
    return ok


def send_message_with_detail(webhook_url: str, content: str,
                              username: str = "Steam Multi-Box"
                              ) -> tuple[bool, str]:
    """Versi send_message yang juga mengembalikan alasan kegagalan.

    Dipakai oleh dialog Pengaturan untuk menampilkan error spesifik ke user.
    """
    if not webhook_url or not webhook_url.strip():
        return False, "URL webhook kosong"
    body = content[:_MAX_CONTENT]
    return _post(webhook_url, {"content": body, "username": username})


def notify_run_start(webhook_url: str, label: str, account_count: int) -> bool:
    return send_message(
        webhook_url,
        f"▶️ **{label}** dimulai — memproses {account_count} akun bergiliran…")


def notify_run_done(webhook_url: str, success: int, failed: int,
                    failures: list[tuple[str, str]] | None = None) -> bool:
    icon = "✅" if failed == 0 else "⚠️"
    lines = [f"{icon} **Selesai** — {success} sukses, {failed} gagal."]
    if failures:
        lines.append("")
        lines.append("**Gagal:**")
        for user, reason in failures[:20]:  # batasi biar tidak overflow
            lines.append(f"• `{user}` — {reason}")
    return send_message(webhook_url, "\n".join(lines))


def notify_login(webhook_url: str, username: str, ok: bool,
                 detail: str = "") -> bool:
    if ok:
        return send_message(webhook_url, f"✅ `{username}` login berhasil")
    suffix = f" — {detail}" if detail else ""
    return send_message(webhook_url, f"❌ `{username}` gagal login{suffix}")


def notify_edit(webhook_url: str, old_username: str,
                new_username: str, password_changed: bool) -> bool:
    if old_username.lower() == new_username.lower():
        what = "password" if password_changed else "(tidak ada perubahan)"
        return send_message(
            webhook_url, f"✏️ Edit credential `{old_username}` — {what} diubah")
    return send_message(
        webhook_url,
        f"✏️ Edit credential — `{old_username}` → `{new_username}` (rename + pw)")
