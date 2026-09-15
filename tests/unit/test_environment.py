from pathlib import Path

from wordvault.diagnostics.environment import EnvironmentInspector


def test_environment_report_contains_only_exportable_summary(tmp_path: Path) -> None:
    report = EnvironmentInspector().inspect(tmp_path)

    assert report["architecture"]
    assert report["os_name"]
    assert isinstance(report["fts5_available"], bool)
    assert report["write_access"] is True
    assert set(report) == {
        "architecture",
        "disk_space_bucket",
        "display_server",
        "distro_id",
        "distro_version",
        "fts5_available",
        "glibc_version",
        "kernel_version",
        "os_name",
        "os_version",
        "sqlite_version",
        "wps_status",
        "wps_version",
        "write_access",
    }


def test_wps_detection_accepts_an_explicit_executable(tmp_path: Path) -> None:
    executable = tmp_path / "wps"
    executable.write_text("", encoding="utf-8")

    report = EnvironmentInspector(wps_candidates=(executable,)).inspect(tmp_path)

    assert report["wps_status"] == "detected"


def test_linux_environment_reports_compatibility_versions_without_machine_details(
    tmp_path: Path,
) -> None:
    os_release = tmp_path / "os-release"
    os_release.write_text(
        'ID="kylin"\nVERSION_ID="V10-SP1-2403"\nPRETTY_NAME="Sensitive Hostname"\n',
        encoding="utf-8",
    )

    inspector = EnvironmentInspector(
        os_release_path=os_release,
        libc_version_getter=lambda: ("glibc", "2.31"),
        environment={"XDG_SESSION_TYPE": "x11", "HOSTNAME": "classified-machine"},
    )
    report = inspector.inspect(tmp_path)

    assert report["distro_id"] == "kylin"
    assert report["distro_version"] == "V10-SP1-2403"
    assert report["glibc_version"] == "2.31"
    assert report["display_server"] == "x11"
    assert "classified-machine" not in repr(report)
    assert "Sensitive Hostname" not in repr(report)
