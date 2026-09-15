#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
package="$script_dir/wordvault_0.1.0_arm64.deb"

if [[ "$(uname -m)" != "aarch64" ]]; then
  echo "安装终止：当前电脑不是 ARM64/aarch64 架构。" >&2
  exit 1
fi
if [[ ! -f "$package" ]]; then
  echo "安装终止：安装脚本旁未找到 wordvault_0.1.0_arm64.deb。" >&2
  exit 1
fi

glibc_version="$(ldd --version 2>&1 | head -n 1 | grep -oE '[0-9]+\.[0-9]+' | tail -n 1)"
if [[ -z "$glibc_version" ]] || ! dpkg --compare-versions "$glibc_version" ge 2.31; then
  echo "安装终止：需要 glibc 2.31 或更高版本，当前检测为 ${glibc_version:-未知}。" >&2
  exit 1
fi

missing=()
dependencies="$(dpkg-deb -f "$package" Depends | tr ',' '\n' | sed 's/^ *//;s/ *$//')"
while IFS= read -r dependency; do
  [[ -z "$dependency" ]] && continue
  if ! dpkg-query -W -f='${Status}' "$dependency" 2>/dev/null | grep -q 'install ok installed'; then
    missing+=("$dependency")
  fi
done <<< "$dependencies"

if (( ${#missing[@]} > 0 )); then
  echo "安装终止：系统缺少以下图形运行库，请由客户管理员从银河麒麟安装介质补齐：" >&2
  printf '  %s\n' "${missing[@]}" >&2
  exit 1
fi

sudo dpkg -i "$package"
echo "文澜资料库安装完成，可从应用菜单启动。"
