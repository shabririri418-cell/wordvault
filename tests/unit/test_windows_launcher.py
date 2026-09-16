from pathlib import Path

from wordvault.windows_launcher import build_child_environment, core_executable


def test_launcher_forces_software_rendering_before_the_gui_process_starts() -> None:
    environment = build_child_environment({"KEEP_ME": "yes", "QT_OPENGL": "desktop"})

    assert environment["KEEP_ME"] == "yes"
    assert environment["QT_OPENGL"] == "software"
    assert environment["QT_QUICK_BACKEND"] == "software"


def test_launcher_finds_the_core_application_beside_it() -> None:
    launcher = Path("C:/preview/文澜资料库.exe")

    assert core_executable(launcher) == Path("C:/preview/_WordVaultCore.exe")
