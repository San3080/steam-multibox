"""Menyusun argumen peluncuran Steam (Pendekatan A: steam.exe -login)."""


def build_login_args(steam_exe: str, username: str, password: str) -> list[str]:
    """Argumen untuk login langsung: steam.exe -login <user> <pass>.

    Dipakai sebagai program+args bagi Sandboxie.launch_cmd.
    """
    return [steam_exe, "-login", username, password]
