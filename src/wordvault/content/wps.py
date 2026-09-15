from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class WpsLauncher:
    def __init__(self, candidates: tuple[Path, ...] | None = None) -> None:
        self.candidates = candidates

    def build_command(self, document: Path) -> list[str]:
        executable = self._find_executable()
        if executable is None:
            raise FileNotFoundError("没有检测到 WPS，请检查安装状态")
        document = document.expanduser().resolve()
        if not document.is_file():
            raise FileNotFoundError("要打开的文档不存在")
        return [str(executable), str(document)]

    def open(self, document: Path) -> None:
        subprocess.Popen(self.build_command(document), shell=False)

    def _find_executable(self) -> Path | None:
        if self.candidates is not None:
            return next((path.resolve() for path in self.candidates if path.is_file()), None)
        detected = shutil.which("wps") or shutil.which("wps-office")
        return Path(detected).resolve() if detected else None

