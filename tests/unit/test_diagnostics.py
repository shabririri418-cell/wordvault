import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from wordvault.diagnostics.service import DiagnosticsService, UnsafeDiagnosticField


def test_rejects_fields_outside_the_diagnostic_whitelist(tmp_path: Path) -> None:
    service = DiagnosticsService(tmp_path)

    with pytest.raises(UnsafeDiagnosticField, match="file_name"):
        service.record("IMPORT_FAILED", file_name="涉密方案.docx")


def test_rejects_sensitive_text_smuggled_through_an_allowed_field(tmp_path: Path) -> None:
    service = DiagnosticsService(tmp_path)

    with pytest.raises(UnsafeDiagnosticField, match="error_code"):
        service.record("IMPORT_FAILED", error_code="涉密方案.docx")


def test_exports_only_whitelisted_diagnostics(tmp_path: Path) -> None:
    service = DiagnosticsService(tmp_path)
    service.record("IMPORT_FAILED", error_code="DOC_PARSE_001", duration_ms=25)

    archive = service.export(tmp_path / "诊断包.zip", environment={"os_name": "Kylin"})

    with zipfile.ZipFile(archive) as package:
        event = json.loads(package.read("events.jsonl").decode("utf-8").strip())
        environment = json.loads(package.read("environment.json").decode("utf-8"))

    assert event["event"] == "IMPORT_FAILED"
    assert event["error_code"] == "DOC_PARSE_001"
    assert environment == {"os_name": "Kylin"}
    assert "涉密" not in archive.read_bytes().decode("latin1")


def test_cleanup_removes_logs_older_than_thirty_days(tmp_path: Path) -> None:
    service = DiagnosticsService(tmp_path)
    old_log = tmp_path / "events-20000101.jsonl"
    old_log.write_text("old", encoding="utf-8")
    old_time = (datetime.now(UTC) - timedelta(days=31)).timestamp()
    old_log.touch()
    import os

    os.utime(old_log, (old_time, old_time))

    service.cleanup()

    assert not old_log.exists()


def test_clear_removes_event_logs_but_not_other_files(tmp_path: Path) -> None:
    service = DiagnosticsService(tmp_path)
    service.record("APP_STARTED", app_version="0.1.0")
    unrelated = tmp_path / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")

    service.clear()

    assert list(tmp_path.glob("events-*.jsonl")) == []
    assert unrelated.exists()
