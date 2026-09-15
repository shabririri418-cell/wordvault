from __future__ import annotations

import os
import platform
import shutil
import sqlite3
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path


class EnvironmentInspector:
    _SAFE_VALUE = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")

    def __init__(
        self,
        wps_candidates: tuple[Path, ...] = (),
        *,
        os_release_path: Path = Path("/etc/os-release"),
        libc_version_getter: Callable[[], tuple[str, str]] = platform.libc_ver,
        environment: Mapping[str, str] = os.environ,
    ) -> None:
        self.wps_candidates = wps_candidates
        self.os_release_path = os_release_path
        self.libc_version_getter = libc_version_getter
        self.environment = environment

    def inspect(self, library_root: Path) -> dict[str, object]:
        wps_path = self._find_wps()
        distro = self._read_os_release()
        libc_name, libc_version = self.libc_version_getter()
        return {
            "architecture": platform.machine() or "unknown",
            "disk_space_bucket": self._disk_space_bucket(library_root),
            "display_server": self._display_server(),
            "distro_id": distro.get("ID", "unknown"),
            "distro_version": distro.get("VERSION_ID", "unknown"),
            "fts5_available": self._fts5_available(),
            "glibc_version": libc_version if libc_name == "glibc" else "unknown",
            "kernel_version": platform.release() or "unknown",
            "os_name": platform.system() or "unknown",
            "os_version": platform.version() or "unknown",
            "sqlite_version": sqlite3.sqlite_version,
            "wps_status": "detected" if wps_path else "not_detected",
            "wps_version": "unknown",
            "write_access": self._is_writable(library_root),
        }

    def _read_os_release(self) -> dict[str, str]:
        try:
            lines = self.os_release_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {}
        result: dict[str, str] = {}
        for line in lines:
            key, separator, raw_value = line.partition("=")
            if separator and key in {"ID", "VERSION_ID"}:
                value = raw_value.strip().strip('"').strip("'")
                result[key] = self._safe_value(value)
        return result

    def _display_server(self) -> str:
        value = self.environment.get("XDG_SESSION_TYPE", "unknown").lower()
        return value if value in {"x11", "wayland", "tty"} else "unknown"

    @classmethod
    def _safe_value(cls, value: str) -> str:
        if value and len(value) <= 64 and all(character in cls._SAFE_VALUE for character in value):
            return value
        return "unknown"

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
