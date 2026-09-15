import json
import zipfile
from pathlib import Path

from wordvault.diagnostics.self_check import SelfCheckService


def test_self_check_exports_only_summary_and_synthetic_results(tmp_path: Path) -> None:
    sensitive_library = tmp_path / "绝密项目资料"
    sensitive_library.mkdir()
    destination = tmp_path / "diagnostics.zip"

    result = SelfCheckService().run(sensitive_library, destination)

    assert result.overall_status == "pass"
    assert destination.is_file()
    with zipfile.ZipFile(destination) as package:
        assert set(package.namelist()) == {
            "collection-structure.json",
            "environment.json",
            "self-check.json",
        }
        report = json.loads(package.read("self-check.json"))
        environment = json.loads(package.read("environment.json"))
    assert report["checks"]["database"] == "pass"
    assert report["checks"]["document_pipeline"] == "pass"
    assert report["checks"]["fts5"] in {"pass", "fail"}
    assert environment["write_access"] is True
    assert "绝密项目资料" not in destination.read_bytes().decode("latin1")


def test_self_check_marks_required_failures_without_exporting_exception_text(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "diagnostics.zip"
    service = SelfCheckService(database_probe=lambda: (_ for _ in ()).throw(RuntimeError("secret")))

    result = service.run(tmp_path, destination)

    assert result.overall_status == "fail"
    with zipfile.ZipFile(destination) as package:
        report_text = package.read("self-check.json").decode("utf-8")
    assert '"database": "fail"' in report_text
    assert "secret" not in report_text
