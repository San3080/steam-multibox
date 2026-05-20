from src.config import AppConfig
from src.logbus import LogBus
from src.accounts import Account
from src.monitor import BoxState
from src.controller import Controller


class FakeDriver:
    """Driver palsu: 'poll' mengembalikan keadaan dari skrip yang ditentukan tes."""

    def __init__(self, states_by_box: dict[str, list]):
        self.states_by_box = states_by_box
        self.calls: list[str] = []

    def ensure_box(self, box):
        self.calls.append(f"ensure:{box}")

    def launch(self, account, box):
        self.calls.append(f"launch:{box}")

    def terminate(self, box):
        self.calls.append(f"terminate:{box}")

    def graceful_shutdown(self, box):
        self.calls.append(f"graceful:{box}")

    def click_add(self):
        self.calls.append("click_add")

    def fill_login(self, account):
        self.calls.append(f"fill:{account.username}")

    def poll(self, box, elapsed, **_):
        return self.states_by_box[box].pop(0)


def make_controller(driver, cfg=None):
    cfg = cfg or AppConfig(max_retries=2, retry_check_delay=0,
                           stagger_seconds=0, splash_timeout=40,
                           poll_interval=0, terminate_grace_seconds=0)
    return Controller(cfg, LogBus(), driver, sleep=lambda s: None)


def test_account_healthy_first_try_succeeds():
    driver = FakeDriver({"Steam_u1": [BoxState.HEALTHY]})
    ctrl = make_controller(driver)
    ok, reason = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is True and reason == ""
    assert "launch:Steam_u1" in driver.calls


def test_account_picker_then_login_form_then_healthy():
    driver = FakeDriver({"Steam_u1": [
        BoxState.ACCOUNT_PICKER, BoxState.LOGIN_FORM, BoxState.HEALTHY]})
    ctrl = make_controller(driver)
    ok, _ = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is True
    assert "click_add" in driver.calls
    assert "fill:u1" in driver.calls


def test_stuck_splash_retries_then_fails():
    driver = FakeDriver({"Steam_u1": [
        BoxState.STUCK_SPLASH, BoxState.STUCK_SPLASH, BoxState.STUCK_SPLASH]})
    ctrl = make_controller(driver)  # max_retries=2 -> 3 attempts total
    ok, reason = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is False
    assert "retry" in reason.lower()
    assert driver.calls.count("terminate:Steam_u1") == 3


def test_stuck_retry_then_recovers():
    driver = FakeDriver({"Steam_u1": [BoxState.STUCK_RETRY, BoxState.HEALTHY]})
    ctrl = make_controller(driver)
    ok, _ = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is True
    assert driver.calls.count("launch:Steam_u1") == 2


def test_waiting_2fa_then_healthy_does_not_terminate():
    driver = FakeDriver({"Steam_u1": [BoxState.WAITING_2FA, BoxState.HEALTHY]})
    ctrl = make_controller(driver)
    ok, _ = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is True
    assert "terminate:Steam_u1" not in driver.calls


def test_run_all_writes_failures(tmp_path, monkeypatch):
    driver = FakeDriver({
        "Steam_u1": [BoxState.HEALTHY],
        "Steam_u2": [BoxState.STUCK_SPLASH, BoxState.STUCK_SPLASH, BoxState.STUCK_SPLASH],
    })
    cfg = AppConfig(max_retries=2, retry_check_delay=0, stagger_seconds=0,
                    poll_interval=0, terminate_grace_seconds=0)
    fail_path = tmp_path / "fail.txt"
    ctrl = Controller(cfg, LogBus(), driver, sleep=lambda s: None,
                      fail_path=str(fail_path))
    summary = ctrl.run_sync([Account("u1", "p1", 1), Account("u2", "p2", 2)])
    assert summary == (1, 1)  # (sukses, gagal)
    content = fail_path.read_text(encoding="utf-8")
    assert content.startswith("u2,p2  # ")


def test_auto_terminate_on_success_terminates_healthy_box():
    """Auto-terminate harus tetap kerja: graceful shutdown dulu lalu hard terminate."""
    driver = FakeDriver({"Steam_u1": [BoxState.HEALTHY]})
    cfg = AppConfig(max_retries=2, retry_check_delay=0, stagger_seconds=0,
                    auto_terminate_on_success=True, poll_interval=0,
                    terminate_grace_seconds=0)
    ctrl = Controller(cfg, LogBus(), driver, sleep=lambda s: None)
    ctrl.run_sync([Account("u1", "p1", 1)])
    assert "graceful:Steam_u1" in driver.calls
    assert "terminate:Steam_u1" in driver.calls
    # Urutan: graceful sebelum terminate
    assert driver.calls.index("graceful:Steam_u1") < driver.calls.index("terminate:Steam_u1")


def test_request_stop_short_circuits_processing():
    """Setelah request_stop, akun belum diproses dilewati."""
    driver = FakeDriver({})  # no states needed — stop comes first
    ctrl = make_controller(driver)
    ctrl.request_stop()
    summary = ctrl.run_sync([Account("u1", "p1", 1), Account("u2", "p2", 2)])
    # tidak ada launch karena di-stop sebelum proses pertama
    assert "launch:Steam_u1" not in driver.calls
    assert summary[0] == 0  # 0 sukses


def test_login_failed_does_not_retry():
    """LOGIN_FAILED harus langsung fail tanpa retry — password salah, retry membabi-buta = bahaya."""
    driver = FakeDriver({"Steam_u1": [BoxState.LOGIN_FAILED]})
    ctrl = make_controller(driver)
    ok, reason = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is False
    assert "menolak" in reason.lower() or "password" in reason.lower()
    assert driver.calls.count("launch:Steam_u1") == 1
    assert driver.calls.count("terminate:Steam_u1") == 1


def test_login_form_filled_only_once_per_attempt():
    """Tidak boleh isi form login berulang-ulang -- Steam akan rate-limit."""
    driver = FakeDriver({"Steam_u1": [
        BoxState.LOGIN_FORM,    # poll 1: fill
        BoxState.LOGIN_FORM,    # poll 2: jangan fill lagi
        BoxState.LOGIN_FORM,    # poll 3: jangan fill lagi
        BoxState.HEALTHY,       # poll 4: sukses
    ]})
    ctrl = make_controller(driver)
    ok, _ = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is True
    assert driver.calls.count("fill:u1") == 1


def test_account_picker_clicked_only_once_per_attempt():
    """Tombol + di picker juga cukup sekali per attempt."""
    driver = FakeDriver({"Steam_u1": [
        BoxState.ACCOUNT_PICKER,  # klik
        BoxState.ACCOUNT_PICKER,  # jangan klik lagi
        BoxState.LOGIN_FORM,
        BoxState.HEALTHY,
    ]})
    ctrl = make_controller(driver)
    ok, _ = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is True
    assert driver.calls.count("click_add") == 1


def test_mismatch_triggers_wipe_and_retry(monkeypatch):
    driver = FakeDriver({"Steam_u1": [BoxState.HEALTHY, BoxState.HEALTHY]})
    verify_results = iter([(False, "akun lain: someone"),
                           (True, "login terverifikasi: u1")])
    monkeypatch.setattr("src.controller.verify_login",
                        lambda box, user: next(verify_results))
    monkeypatch.setattr("src.controller.find_box_root", lambda box: "/fake")
    monkeypatch.setattr("src.controller.wipe_steam_session", lambda root: (1, ["x"]))
    ctrl = make_controller(driver)
    ok, _ = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is True
    assert driver.calls.count("launch:Steam_u1") == 2


def test_each_attempt_primes_clean_state(monkeypatch):
    """Tiap launch attempt harus pakai prime_clean_steam_config dulu."""
    driver = FakeDriver({"Steam_u1": [BoxState.HEALTHY]})
    cfg = AppConfig(max_retries=2, retry_check_delay=0, stagger_seconds=0,
                    poll_interval=0, terminate_grace_seconds=0)
    monkeypatch.setattr("src.controller.find_box_root", lambda b: "/fake/root")
    primed = []
    monkeypatch.setattr("src.controller.prime_clean_steam_config",
                        lambda root: (primed.append(root), 0)[1])
    ctrl = Controller(cfg, LogBus(), driver, sleep=lambda s: None)
    ok, _ = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is True
    # SETIDAKNYA 1 prime di attempt pertama
    assert primed == ["/fake/root"]


def test_ui_login_method_skips_login_args(monkeypatch):
    """SteamBoxDriver.launch untuk login_method='ui' panggil launch polos
    (tanpa -login args). Kita observasi via mock subprocess.launch."""
    from src.controller import SteamBoxDriver
    from src.config import AppConfig
    cfg = AppConfig(login_method="ui", steam_exe=r"D:\steam.exe",
                    sandboxie_dir=r"D:\sb")
    driver = SteamBoxDriver(cfg)
    captured = {}
    def fake_launch(box, program, args=None):
        captured["box"] = box
        captured["program"] = program
        captured["args"] = args
    monkeypatch.setattr(driver.sandboxie, "launch", fake_launch)
    driver.launch(Account("u1", "p1", 1), "Steam_u1")
    # Tidak ada args -login
    assert captured["box"] == "Steam_u1"
    assert captured["program"] == r"D:\steam.exe"
    # args boleh None atau [] -- pokoknya bukan -login
    assert not captured["args"] or "-login" not in (captured["args"] or [])


def test_cmdline_login_method_passes_login_args(monkeypatch):
    """SteamBoxDriver.launch untuk login_method='cmdline' tetap pakai -login."""
    from src.controller import SteamBoxDriver
    from src.config import AppConfig
    cfg = AppConfig(login_method="cmdline", steam_exe=r"D:\steam.exe",
                    sandboxie_dir=r"D:\sb")
    driver = SteamBoxDriver(cfg)
    captured = {}
    def fake_launch(box, program, args=None):
        captured["args"] = args
    monkeypatch.setattr(driver.sandboxie, "launch", fake_launch)
    driver.launch(Account("u1", "p1", 1), "Steam_u1")
    assert "-login" in (captured["args"] or [])
    assert "u1" in (captured["args"] or [])


def test_persistent_mismatch_eventually_fails(monkeypatch):
    driver = FakeDriver({"Steam_u1": [BoxState.HEALTHY] * 4})
    monkeypatch.setattr("src.controller.verify_login",
                        lambda box, user: (False, "selalu salah"))
    monkeypatch.setattr("src.controller.find_box_root", lambda box: "/fake")
    monkeypatch.setattr("src.controller.wipe_steam_session", lambda root: (0, []))
    ctrl = make_controller(driver)
    ok, reason = ctrl.process_account(Account("u1", "p1", 1))
    assert ok is False
    assert driver.calls.count("launch:Steam_u1") == 3  # max_retries=2 + 1
