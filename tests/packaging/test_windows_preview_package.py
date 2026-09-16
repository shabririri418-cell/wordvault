import zipfile
from pathlib import Path


def test_windows_preview_is_single_file_app_that_can_run_after_normal_extraction() -> None:
    archive = (
        Path(__file__).resolve().parents[2]
        / "dist"
        / "windows-preview"
        / "文澜资料库-Windows预览测试包.zip"
    )

    with zipfile.ZipFile(archive) as package:
        names = package.namelist()

    assert "文澜资料库.exe" in names
    assert not any("_internal/" in name for name in names)
    assert len([name for name in names if name.endswith(".docx")]) == 64


def test_windows_bundle_does_not_collect_dlls_from_unrelated_tool_runtimes() -> None:
    package_manifest = (
        Path(__file__).resolve().parents[2]
        / "build"
        / "windows-preview"
        / "work"
        / "WordVault.windows"
        / "PKG-00.toc"
    ).read_text(encoding="utf-8")

    assert "native\\\\libheif" not in package_manifest
    assert "ucrtbase.dll" not in package_manifest
