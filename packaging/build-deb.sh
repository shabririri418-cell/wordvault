#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -m)" != "aarch64" ]]; then
  echo "必须在 AArch64 构建机上生成客户安装包。" >&2
  exit 1
fi

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
build_requirements="${BUILD_REQUIREMENTS:-requirements-build.txt}"

python3 -m venv .venv-build
.venv-build/bin/python -m pip install \
  --no-index --find-links vendor/wheels -r "$build_requirements"
.venv-build/bin/python -m pytest -q --ignore=tests/packaging
.venv-build/bin/python -m ruff check .
.venv-build/bin/pyinstaller \
  --noconfirm --clean --windowed --onedir \
  --name WordVault --paths src src/wordvault/__main__.py

verification_root="$(mktemp -d)"
trap 'rm -rf -- "$verification_root"' EXIT
dist/WordVault/WordVault \
  --self-check \
  --library-root "$verification_root" \
  --output "$verification_root/self-check.zip"
test -s "$verification_root/self-check.zip"

stage="$project_root/build/deb-root"
if [[ -d "$stage" ]]; then
  find "$stage" -mindepth 1 -delete
fi
mkdir -p \
  "$stage/DEBIAN" \
  "$stage/opt/wordvault" \
  "$stage/usr/share/applications" \
  "$stage/usr/share/icons/hicolor/scalable/apps"
cp -a dist/WordVault/. "$stage/opt/wordvault/"
if [[ -f vendor/tika/tika-app.jar ]]; then
  mkdir -p "$stage/opt/wordvault/resources"
  cp vendor/tika/tika-app.jar "$stage/opt/wordvault/resources/tika-app.jar"
fi
cp packaging/wordvault.desktop "$stage/usr/share/applications/wordvault.desktop"
cp packaging/wordvault.svg "$stage/usr/share/icons/hicolor/scalable/apps/wordvault.svg"

cat > "$stage/DEBIAN/control" <<'CONTROL'
Package: wordvault
Version: 0.1.0
Section: office
Priority: optional
Architecture: arm64
Maintainer: WordVault Team
Depends: libdbus-1-3, libegl1, libfontconfig1, libgl1, libx11-6, libx11-xcb1, libxcb1, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxext6, libxi6, libxkbcommon0, libxkbcommon-x11-0, libxrender1
Description: 完全离线的 Word 文档管理工具
CONTROL

dpkg-deb --build "$stage" "$project_root/dist/wordvault_0.1.0_arm64.deb"
echo "已生成 dist/wordvault_0.1.0_arm64.deb"
