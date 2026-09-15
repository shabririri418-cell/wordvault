from __future__ import annotations

import json
import re
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path


class UnsafeDiagnosticField(ValueError):
    """Raised when unapproved information is submitted to diagnostics."""


class DiagnosticsService:
    RETENTION_DAYS = 30
    MAX_TOTAL_BYTES = 100 * 1024 * 1024
    EVENT_FIELDS = frozenset(
        {
            "app_version",
            "component_version",
            "confidence_bucket",
            "count",
            "diagnostic_id",
            "duration_ms",
            "error_code",
            "exit_code",
            "format",
            "model_version",
            "rule_id",
            "size_bucket",
            "stage",
            "status",
        }
    )
    ENVIRONMENT_FIELDS = frozenset(
        {
            "app_version",
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
    )
    _SAFE_EVENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
    _SAFE_EVENT_VALUE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")

    def __init__(self, log_directory: Path) -> None:
        self.log_directory = log_directory.resolve()
        self.log_directory.mkdir(parents=True, exist_ok=True)

    def record(self, event: str, **fields: object) -> None:
        self._validate_event(event)
        self._validate_keys(fields, self.EVENT_FIELDS)
        self._validate_event_values(fields)
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            **fields,
        }
        log_path = self.log_directory / f"events-{datetime.now(UTC):%Y%m%d}.jsonl"
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n")
        self.cleanup()

    def export(self, destination: Path, environment: dict[str, object]) -> Path:
        self._validate_keys(environment, self.ENVIRONMENT_FIELDS)
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as package:
            event_lines = []
            for log_path in sorted(self.log_directory.glob("events-*.jsonl")):
                event_lines.extend(log_path.read_text(encoding="utf-8").splitlines())
            package.writestr("events.jsonl", "\n".join(event_lines))
            package.writestr(
                "environment.json",
                json.dumps(environment, ensure_ascii=True, indent=2, sort_keys=True),
            )
        return destination

    def clear(self) -> None:
        for log_path in self.log_directory.glob("events-*.jsonl"):
            log_path.unlink(missing_ok=True)

    def cleanup(self) -> None:
        cutoff = datetime.now(UTC) - timedelta(days=self.RETENTION_DAYS)
        logs = sorted(
            self.log_directory.glob("events-*.jsonl"), key=lambda path: path.stat().st_mtime
        )
        for log_path in logs:
            modified = datetime.fromtimestamp(log_path.stat().st_mtime, UTC)
            if modified < cutoff:
                log_path.unlink(missing_ok=True)

        logs = sorted(
            self.log_directory.glob("events-*.jsonl"), key=lambda path: path.stat().st_mtime
        )
        total = sum(path.stat().st_size for path in logs)
        for log_path in logs:
            if total <= self.MAX_TOTAL_BYTES:
                break
            size = log_path.stat().st_size
            log_path.unlink(missing_ok=True)
            total -= size

    @classmethod
    def _validate_event(cls, event: str) -> None:
        if not cls._SAFE_EVENT_NAME.fullmatch(event):
            raise UnsafeDiagnosticField("事件编号格式不安全")

    @staticmethod
    def _validate_keys(fields: dict[str, object], allowed: frozenset[str]) -> None:
        unknown = sorted(set(fields) - allowed)
        if unknown:
            raise UnsafeDiagnosticField(f"诊断字段不在白名单中: {', '.join(unknown)}")

    @classmethod
    def _validate_event_values(cls, fields: dict[str, object]) -> None:
        for key, value in fields.items():
            if isinstance(value, str) and not cls._SAFE_EVENT_VALUE.fullmatch(value):
                raise UnsafeDiagnosticField(f"诊断字段 {key} 的值不安全")
            if not isinstance(value, (str, int, float, bool)):
                raise UnsafeDiagnosticField(f"诊断字段 {key} 的类型不安全")
