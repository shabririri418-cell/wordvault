#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -m)" != "aarch64" ]]; then
  echo "必须在 AArch64 构建机上生成客户安装包。" >&2
  exit 1
fi

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python3 -m venv .venv-build
.venv-build/bin/python -m pip install \
  --no-index --find-links vendor/wheels -r requirements-build.txt
.venv-build/bin/python -m pytest -q
.venv-build/bin/python -m ruff check .
.venv-build/bin/pyinstaller \
  --noconfirm --clean --windowed --onedir \
  --name WordVault --paths src src/wordvault/__main__.py

stage="$project_root/build/deb-root"
if [[ -d "$stage" ]]; then
  find "$stage" -mindepth 1 -delete
fi
mkdir -p "$stage/DEBIAN" "$stage/opt/wordvault" "$stage/usr/share/applications"
cp -a dist/WordVault/. "$stage/opt/wordvault/"
cp packaging/wordvault.desktop "$stage/usr/share/applications/wordvault.desktop"

cat > "$stage/DEBIAN/control" <<'CONTROL'
Package: wordvault
Version: 0.1.0
Section: office
Priority: optional
Architecture: arm64
Maintainer: WordVault Team
Description: 完全离线的 Word 文档管理工具
CONTROL

dpkg-deb --build "$stage" "$project_root/dist/wordvault_0.1.0_arm64.deb"
echo "已生成 dist/wordvault_0.1.0_arm64.deb"

