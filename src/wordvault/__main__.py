from __future__ import annotations

import argparse
import tempfile
from collections.abc import Sequence
from pathlib import Path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wordvault")
    parser.add_argument("--self-check", action="store_true", help="运行离线环境自检")
    parser.add_argument("--gui-smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--window-smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--library-root", type=Path, help="要检测读写能力的资料库目录")
    parser.add_argument("--output", type=Path, help="诊断包输出位置")
    arguments = parser.parse_args(argv)
    if arguments.gui_smoke_test:
        from PySide6.QtCore import qVersion
        from PySide6.QtWidgets import QApplication

        application = QApplication.instance() or QApplication([])
        return 0 if application and qVersion() else 1
    if arguments.window_smoke_test:
        from PySide6.QtWidgets import QApplication

        from wordvault.storage.database import LibraryDatabase
        from wordvault.ui.main_window import MainWindow

        application = QApplication.instance() or QApplication([])
        with (
            tempfile.TemporaryDirectory(prefix="wordvault-window-check-") as directory,
            LibraryDatabase.open(Path(directory) / "library") as database,
        ):
            window = MainWindow(database)
            window.show()
            application.processEvents()
            visible = window.isVisible()
            window.close()
        return 0 if visible else 1
    if arguments.self_check:
        from wordvault.diagnostics.self_check import SelfCheckService

        library_root = (arguments.library_root or Path.cwd()).expanduser().resolve()
        output = (arguments.output or Path.cwd() / "wordvault-diagnostics.zip").expanduser()
        result = SelfCheckService().run(library_root, output)
        return 0 if result.overall_status == "pass" else 2

    from wordvault.app import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
