import zipfile
from pathlib import Path


def test_windows_preview_keeps_the_complete_runtime_beside_the_executable() -> None:
    archive = (
        Path(__file__).resolve().parents[2]
        / "dist"
        / "windows-preview"
        / "文澜资料库-Windows预览测试包.zip"
    )

    with zipfile.ZipFile(archive) as package:
        names = package.namelist()

    package_root = "文澜资料库-Windows预览版/"
    assert f"{package_root}文澜资料库.exe" in names
    assert f"{package_root}_WordVaultCore.exe" in names
    assert any(
        name.startswith(f"{package_root}_internal/PySide6/")
        and name.endswith("QtCore.pyd")
        for name in names
    )
    assert all(name.startswith(package_root) for name in names)
    assert len([name for name in names if name.endswith(".docx")]) == 64


def test_windows_bundle_does_not_collect_dlls_from_unrelated_tool_runtimes() -> None:
    package_manifest = (
        Path(__file__).resolve().parents[2]
        / "build"
        / "windows-preview"
        / "work"
        / "WordVault.windows"
        / "COLLECT-00.toc"
    ).read_text(encoding="utf-8")

    assert "native\\\\libheif" not in package_manifest
    assert "ucrtbase.dll" not in package_manifest
