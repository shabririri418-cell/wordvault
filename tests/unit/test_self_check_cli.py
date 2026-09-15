import zipfile
from pathlib import Path

from wordvault.__main__ import main


def test_self_check_cli_creates_requested_diagnostic_package(tmp_path: Path) -> None:
    destination = tmp_path / "result.zip"

    exit_code = main(
        ["--self-check", "--library-root", str(tmp_path), "--output", str(destination)]
    )

    assert exit_code == 0
    with zipfile.ZipFile(destination) as package:
        assert "self-check.json" in package.namelist()
