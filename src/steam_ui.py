"""Otomasi jendela Steam: deteksi keadaan, klik '+', isi form login.

Memakai pywinauto. Fungsi snapshot/aksi mengembalikan hasil terbaik-usaha;
kegagalan akses jendela ditangani pemanggil (controller -> konfirmasi manual).
"""
from src.monitor import WindowSnapshot

# Penanda judul/teks jendela. Dipisah agar mudah disesuaikan saat Steam berubah.
_PICKER_TITLES = ("who's playing", "steam")
_LOGIN_TITLES = ("sign in to steam",)


def is_account_picker_title(title: str) -> bool:
    return any(t in title.lower() for t in _PICKER_TITLES)


def is_login_form_title(title: str) -> bool:
    return any(t in title.lower() for t in _LOGIN_TITLES)


def _connect_desktop():
    """Ambil objek Desktop pywinauto. Dipisah agar bisa di-mock saat tes."""
    from pywinauto import Desktop
    return Desktop(backend="uia")


def snapshot_box(box: str, elapsed: float, debug_log=None,
                 expected_username: str | None = None) -> WindowSnapshot:
    """Bangun WindowSnapshot dari jendela Steam DI DALAM box Sandboxie.

    Strategi:
      1. Cek `loginusers.vdf` di folder box. Kalau AccountName cocok dengan
         `expected_username`, Steam pasti sudah login akun yang benar -> Healthy.
         (Filesystem lebih andal daripada title-scraping Chromium.)
      2. Kalau VDF belum tersedia, fallback ke deteksi berbasis judul jendela.

    Sandboxie (Classic default) menambahkan `[#]` ke title bar setiap jendela
    proses sandboxed. Plus juga punya prefix `[<BoxName>]`. Kita filter hanya
    jendela ber-marker itu agar tidak ikut membaca Steam host.

    `debug_log(msg)` opsional dipanggil dengan ringkasan judul jendela.
    """
    snap = WindowSnapshot(elapsed=elapsed)
    # Fast-path: kalau file Steam di disk sudah berisi akun yang diharapkan,
    # box ini PASTI sudah login dengan benar — title-scraping bisa dilewati.
    if expected_username:
        try:
            from src.login_verify import (find_box_root, find_loginusers_vdf,
                                          parse_account_names)
            root = find_box_root(box)
            if root:
                vdf = find_loginusers_vdf(root)
                if vdf:
                    with open(vdf, encoding="utf-8", errors="replace") as f:
                        names = [n.lower() for n in parse_account_names(f.read())]
                    if expected_username.lower() in names:
                        snap.main_window = True
                        if debug_log:
                            debug_log(f"healthy via vdf: {expected_username}")
                        return snap
        except Exception:
            pass  # best-effort; lanjut ke deteksi judul

    try:
        desktop = _connect_desktop()
        titles = [w.window_text() for w in desktop.windows()]
    except Exception:
        return snap

    # Sandboxie Classic menandai title dengan `[#]`; Plus tidak menambahkan
    # apa pun. Kita coba filter dulu — kalau ada hasil, pakai itu. Kalau tidak
    # ada satupun marker yang cocok, JANGAN langsung anggap splash; analisis
    # semua title (pemakai diharapkan menutup Steam host dulu, lihat tombol
    # "Tutup Steam Host" di UI).
    box_marker = f"[{box.lower()}]"
    sandboxed = [t for t in titles if "[#]" in t or box_marker in t.lower()]
    analyzed = sandboxed if sandboxed else titles

    if debug_log:
        ne = [t for t in titles if t and t.strip()]
        sb = [t for t in sandboxed if t and t.strip()]
        debug_log(f"titles={ne[:8]} sandboxed={sb[:8]} mode="
                  f"{'strict' if sandboxed else 'relaxed (no marker found)'}")

    texts = " | ".join(analyzed).lower()

    if "sign in to steam" in texts:
        snap.login_form = True
    if "who's playing" in texts:
        snap.account_picker = True
    if "steam guard" in texts:
        snap.guard_prompt = True

    # Pesan error Steam saat password ditolak — JANGAN retry, langsung fail.
    login_fail_markers = (
        "please check your password",
        "check your password and account name",
        "incorrect password",
        "too many sign in failures",
        "too many retries",
        "something went wrong while attempting to sign",
    )
    if any(m in texts for m in login_fail_markers):
        snap.login_failed = True

    if "retry" in texts or "could not connect" in texts:
        snap.retry_error = True

    # Healthy hanya kalau ada penanda kuat pasca-login.
    healthy_markers = ("library", "store page", "friends list", "your library")
    if any(m in texts for m in healthy_markers) and not snap.login_form:
        snap.main_window = True

    if not any([snap.main_window, snap.login_form, snap.account_picker,
                snap.guard_prompt, snap.retry_error, snap.login_failed]):
        snap.splash_only = True
    return snap


def click_add_account() -> bool:
    """Klik tombol '+' di layar pemilih akun. True jika berhasil."""
    try:
        desktop = _connect_desktop()
        win = desktop.window(title_re=".*Steam.*")
        win.child_window(title="+", control_type="Button").click_input()
        return True
    except Exception:
        return False


def fill_login_form(username: str, password: str) -> bool:
    """Isi form 'Sign in to Steam' DENGAN 'Remember me' tercentang lalu submit.

    Steam menyimpan token enkripsi auto-login hanya kalau Remember me dicentang
    saat login form. Tanpa itu, manual reopen box akan minta password lagi.
    """
    try:
        desktop = _connect_desktop()
        win = desktop.window(title_re=".*Sign in to Steam.*")
        # Pastikan "Remember me" tercentang. Form pakai Chromium -- toggle button
        # name kadang "Remember me" / "Remember password" tergantung versi Steam.
        for name_re in (".*[Rr]emember.*",):
            try:
                cb = win.child_window(title_re=name_re, control_type="CheckBox")
                if cb.exists(timeout=2) and not cb.get_toggle_state():
                    cb.click_input()
                    break
            except Exception:
                continue

        edits = win.descendants(control_type="Edit")
        if len(edits) < 2:
            return False
        edits[0].set_edit_text(username)
        edits[1].set_edit_text(password)
        # Tombol Sign in biasanya satu-satunya button utama selain checkbox.
        try:
            btn = win.child_window(title_re=".*[Ss]ign\\s*in.*",
                                   control_type="Button")
            btn.click_input()
        except Exception:
            win.child_window(control_type="Button", found_index=0).click_input()
        return True
    except Exception:
        return False
