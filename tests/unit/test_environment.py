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
        "fts5_available",
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

