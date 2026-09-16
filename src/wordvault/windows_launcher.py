from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path


def build_child_environment(source: Mapping[str, str]) -> dict[str, str]:
    environment = dict(source)
    environment["QT_OPENGL"] = "software"
    environment["QT_QUICK_BACKEND"] = "software"
    return environment


def core_executable(launcher: Path) -> Path:
    return launcher.with_name("_WordVaultCore.exe")


def main() -> int:
    executable = core_executable(Path(sys.executable))
    if not executable.is_file():
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            "程序文件不完整，请重新解压整个测试包后再运行。",
            "文澜资料库",
            0x10,
        )
        return 1
    completed = subprocess.run(
        [str(executable), *sys.argv[1:]],
        cwd=executable.parent,
        env=build_child_environment(os.environ),
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
