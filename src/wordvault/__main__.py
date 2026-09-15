from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wordvault")
    parser.add_argument("--self-check", action="store_true", help="运行离线环境自检")
    parser.add_argument("--library-root", type=Path, help="要检测读写能力的资料库目录")
    parser.add_argument("--output", type=Path, help="诊断包输出位置")
    arguments = parser.parse_args(argv)
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
