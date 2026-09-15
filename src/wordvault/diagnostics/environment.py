from __future__ import annotations

import os
import platform
import shutil
import sqlite3
import tempfile
from pathlib import Path


class EnvironmentInspector:
    def __init__(self, wps_candidates: tuple[Path, ...] = ()) -> None:
        self.wps_candidates = wps_candidates

    def inspect(self, library_root: Path) -> dict[str, object]:
        wps_path = self._find_wps()
        return {
            "architecture": platform.machine() or "unknown",
            "disk_space_bucket": self._disk_space_bucket(library_root),
            "fts5_available": self._fts5_available(),
            "kernel_version": platform.release() or "unknown",
            "os_name": platform.system() or "unknown",
            "os_version": platform.version() or "unknown",
            "sqlite_version": sqlite3.sqlite_version,
            "wps_status": "detected" if wps_path else "not_detected",
            "wps_version": "unknown",
            "write_access": self._is_writable(library_root),
        }

    def _find_wps(self) -> Path | None:
        for candidate in self.wps_candidates:
            if candidate.is_file():
                return candidate
        executable = shutil.which("wps") or shutil.which("wps-office")
        return Path(executable) if executable else None

    @staticmethod
    def _fts5_available() -> bool:
        try:
            connection = sqlite3.connect(":memory:")
            connection.execute("CREATE VIRTUAL TABLE probe USING fts5(value)")
            connection.close()
            return True
        except sqlite3.DatabaseError:
            return False

    @staticmethod
    def _disk_space_bucket(path: Path) -> str:
        try:
            free = shutil.disk_usage(path).free
        except OSError:
            return "unknown"
        gib = free / (1024**3)
        if gib < 1:
            return "under_1_gib"
        if gib < 10:
            return "1_to_10_gib"
        if gib < 50:
            return "10_to_50_gib"
        return "over_50_gib"

    @staticmethod
    def _is_writable(path: Path) -> bool:
        try:
            descriptor, probe = tempfile.mkstemp(prefix=".write-probe-", dir=path)
            os.close(descriptor)
            Path(probe).unlink(missing_ok=True)
            return True
        except OSError:
            return False

