from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from wordvault.content.parsers import DocxParser
from wordvault.diagnostics.environment import EnvironmentInspector
from wordvault.storage.database import LibraryDatabase


@dataclass(frozen=True)
class SelfCheckResult:
    overall_status: str
    checks: dict[str, str]
    destination: Path


class SelfCheckService:
    """Run synthetic offline checks and export a deliberately path-free report."""

    def __init__(
        self,
        *,
        inspector: EnvironmentInspector | None = None,
        database_probe: Callable[[], None] | None = None,
        document_probe: Callable[[], None] | None = None,
        event_log_directory: Path | None = None,
    ) -> None:
        self.inspector = inspector or EnvironmentInspector()
        self.database_probe = database_probe or self._probe_database
        self.document_probe = document_probe or self._probe_document_pipeline
        self.event_log_directory = event_log_directory

    def run(self, library_root: Path, destination: Path) -> SelfCheckResult:
        environment = self.inspector.inspect(library_root)
        checks = {
            "architecture": "pass"
            if environment["architecture"] in {"aarch64", "arm64", "AMD64", "x86_64"}
            else "fail",
            "database": self._run_probe(self.database_probe),
            "document_pipeline": self._run_probe(self.document_probe),
            "fts5": "pass" if environment["fts5_available"] else "fail",
            "library_write": "pass" if environment["write_access"] else "fail",
        }
        required = ("architecture", "database", "document_pipeline", "library_write")
        overall_status = "pass" if all(checks[key] == "pass" for key in required) else "fail"
        destination = destination.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        report = {"schema_version": 1, "overall_status": overall_status, "checks": checks}
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr("environment.json", self._json(environment))
            package.writestr("self-check.json", self._json(report))
            if self.event_log_directory is not None:
                lines = []
                for log_path in sorted(self.event_log_directory.glob("events-*.jsonl")):
                    lines.extend(log_path.read_text(encoding="utf-8").splitlines())
                package.writestr("events.jsonl", "\n".join(lines))
        return SelfCheckResult(overall_status, checks, destination)

    @staticmethod
    def _run_probe(probe: Callable[[], None]) -> str:
        try:
            probe()
            return "pass"
        except Exception:  # The report intentionally does not expose exception text.
            return "fail"

    @staticmethod
    def _probe_database() -> None:
        with (
            tempfile.TemporaryDirectory(prefix="wordvault-check-") as directory,
            LibraryDatabase.open(Path(directory)) as database,
        ):
            if database.schema_version != LibraryDatabase.CURRENT_SCHEMA_VERSION:
                raise sqlite3.DatabaseError("schema probe failed")

    @staticmethod
    def _probe_document_pipeline() -> None:
        xml = (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>offline-probe</w:t></w:r></w:p></w:body></w:document>"
        )
        with tempfile.TemporaryDirectory(prefix="wordvault-check-") as directory:
            document = Path(directory) / "probe.docx"
            with zipfile.ZipFile(document, "w") as package:
                package.writestr("word/document.xml", xml)
            if DocxParser().parse(document).text != "offline-probe":
                raise ValueError("document probe failed")

    @staticmethod
    def _json(value: object) -> str:
        return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True)
