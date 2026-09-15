from pathlib import Path

import pytest

from wordvault.content.wps import WpsLauncher


def test_builds_wps_command_without_a_shell(tmp_path: Path) -> None:
    executable = tmp_path / "wps"
    executable.write_bytes(b"")
    document = tmp_path / "带 空格.docx"
    document.write_bytes(b"")

    command = WpsLauncher(candidates=(executable,)).build_command(document)

    assert command == [str(executable.resolve()), str(document.resolve())]


def test_reports_missing_wps() -> None:
    with pytest.raises(FileNotFoundError, match="WPS"):
        WpsLauncher(candidates=()).build_command(Path("missing.docx"))

