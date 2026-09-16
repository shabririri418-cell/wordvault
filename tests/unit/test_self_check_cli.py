import zipfile
from pathlib import Path

from wordvault.__main__ import _configure_qt_runtime, main


def test_windows_runtime_defaults_to_software_rendering() -> None:
    environment: dict[str, str] = {}

    _configure_qt_runtime("win32", environment)

    assert environment["QT_OPENGL"] == "software"
    assert environment["QT_QUICK_BACKEND"] == "software"


def test_windows_runtime_preserves_an_explicit_rendering_choice() -> None:
    environment = {"QT_OPENGL": "desktop", "QT_QUICK_BACKEND": "rhi"}

    _configure_qt_runtime("win32", environment)

    assert environment == {"QT_OPENGL": "desktop", "QT_QUICK_BACKEND": "rhi"}


def test_non_windows_runtime_is_not_changed() -> None:
    environment: dict[str, str] = {}

    _configure_qt_runtime("linux", environment)

    assert environment == {}


def test_self_check_cli_creates_requested_diagnostic_package(tmp_path: Path) -> None:
    destination = tmp_path / "result.zip"

    exit_code = main(
        ["--self-check", "--library-root", str(tmp_path), "--output", str(destination)]
    )

    assert exit_code == 0
    with zipfile.ZipFile(destination) as package:
        assert "self-check.json" in package.namelist()


def test_gui_smoke_check_loads_qt_without_opening_the_main_window() -> None:
    assert main(["--gui-smoke-test"]) == 0


def test_window_smoke_check_constructs_the_complete_main_window() -> None:
    assert main(["--window-smoke-test"]) == 0
