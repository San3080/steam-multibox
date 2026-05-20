from unittest.mock import patch
from src import detect


def test_detect_sandboxie_from_service_image_path():
    """Path service SbieSvc -> folder instalasi (paling andal)."""
    with patch.object(detect, "_dir_from_service_image_path",
                      return_value=r"E:\MySbie"), \
         patch.object(detect, "_dir_has_tools",
                      side_effect=lambda d: d == r"E:\MySbie"):
        assert detect.detect_sandboxie_dir() == r"E:\MySbie"


def test_detect_sandboxie_from_registry():
    """Service tidak tersedia, jatuh ke InstallLocation registry classic."""
    with patch.object(detect, "_dir_from_service_image_path", return_value=None), \
         patch.object(detect, "_read_reg", return_value=r"E:\Sbie"), \
         patch.object(detect, "_dir_has_tools", side_effect=lambda d: d == r"E:\Sbie"):
        assert detect.detect_sandboxie_dir() == r"E:\Sbie"


def test_detect_sandboxie_falls_back_to_known_folders():
    """Service & registry gagal -> coba C:\\Program Files\\Sandboxie (default umum)."""
    with patch.object(detect, "_dir_from_service_image_path", return_value=None), \
         patch.object(detect, "_read_reg", return_value=None), \
         patch.object(detect, "_fixed_drives", return_value=["C:"]), \
         patch.object(detect, "_dir_has_tools",
                      side_effect=lambda d: d == r"C:\Program Files\Sandboxie"):
        assert detect.detect_sandboxie_dir() == r"C:\Program Files\Sandboxie"


def test_detect_sandboxie_finds_install_on_non_c_drive():
    """Sandboxie di D:\\Program Files\\Sandboxie-Plus harus ketemu lewat scan drive."""
    with patch.object(detect, "_dir_from_service_image_path", return_value=None), \
         patch.object(detect, "_read_reg", return_value=None), \
         patch.object(detect, "_fixed_drives", return_value=["C:", "D:"]), \
         patch.object(detect, "_dir_has_tools",
                      side_effect=lambda d: d == r"D:\Program Files\Sandboxie-Plus"):
        assert detect.detect_sandboxie_dir() == r"D:\Program Files\Sandboxie-Plus"


def test_detect_sandboxie_returns_none_when_not_found():
    with patch.object(detect, "_dir_from_service_image_path", return_value=None), \
         patch.object(detect, "_read_reg", return_value=None), \
         patch.object(detect, "_fixed_drives", return_value=["C:", "D:"]), \
         patch.object(detect, "_dir_has_tools", return_value=False):
        assert detect.detect_sandboxie_dir() is None


def test_dir_from_service_image_path_parses_quoted_arg():
    raw = r'"D:\Sandboxie\SbieSvc.exe" -arg'
    with patch.object(detect, "_read_reg", return_value=raw):
        assert detect._dir_from_service_image_path() == r"D:\Sandboxie"


def test_dir_from_service_image_path_parses_unquoted():
    with patch.object(detect, "_read_reg",
                      return_value=r"C:\Program Files\Sandboxie\SbieSvc.exe"):
        assert detect._dir_from_service_image_path() == r"C:\Program Files\Sandboxie"


def test_dir_from_service_image_path_returns_none_when_missing():
    with patch.object(detect, "_read_reg", return_value=None):
        assert detect._dir_from_service_image_path() is None


def test_detect_steam_from_registry():
    with patch.object(detect, "_read_reg", return_value=r"D:\Steam"), \
         patch("os.path.isfile", side_effect=lambda p: p == r"D:\Steam\steam.exe"):
        assert detect.detect_steam_exe() == r"D:\Steam\steam.exe"


def test_detect_steam_finds_install_on_non_c_drive():
    """Steam di D:\\Program Files (x86)\\Steam harus ketemu lewat scan drive."""
    expected = r"D:\Program Files (x86)\Steam\steam.exe"
    with patch.object(detect, "_read_reg", return_value=None), \
         patch.object(detect, "_fixed_drives", return_value=["C:", "D:"]), \
         patch("os.path.isfile", side_effect=lambda p: p == expected):
        assert detect.detect_steam_exe() == expected


def test_detect_steam_returns_none_when_not_found():
    with patch.object(detect, "_read_reg", return_value=None), \
         patch.object(detect, "_fixed_drives", return_value=["C:", "D:"]), \
         patch("os.path.isfile", return_value=False):
        assert detect.detect_steam_exe() is None
