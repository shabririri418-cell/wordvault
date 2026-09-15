#!/usr/bin/env bash
set -u

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
package="$script_dir/wordvault_0.1.0_arm64.deb"
result_file="$script_dir/安装结果.txt"

show_message() {
  local kind="$1"
  local message
  message="$(printf '%b' "$2")"
  if command -v zenity >/dev/null 2>&1; then
    zenity "--$kind" --title="文澜资料库安装" --width=460 --text="$message"
  elif command -v kdialog >/dev/null 2>&1; then
    if [[ "$kind" == "error" ]]; then
      kdialog --error "$message" --title "文澜资料库安装"
    else
      kdialog --msgbox "$message" --title "文澜资料库安装"
    fi
  else
    xmessage -center "$message" 2>/dev/null || true
  fi
}

fail() {
  printf '%s\n' "$2" > "$result_file" 2>/dev/null || true
  show_message error "$1\n\n请将同目录下的“安装结果.txt”拍照或发给技术人员。"
  exit 1
}

[[ "$(uname -m)" == "aarch64" ]] || fail "这个安装包只支持飞腾 ARM64 电脑。" "architecture_check_failed"
[[ -f "$package" ]] || fail "安装包不完整，请重新复制整个交付文件夹。" "package_missing"

if [[ -f "$script_dir/SHA256SUMS" ]]; then
  (cd "$script_dir" && sha256sum --check --status SHA256SUMS) \
    || fail "安装包校验失败，文件可能未复制完整。" "checksum_failed"
fi

glibc_version="$(ldd --version 2>&1 | head -n 1 | grep -oE '[0-9]+\.[0-9]+' | tail -n 1)"
if [[ -z "$glibc_version" ]] || ! dpkg --compare-versions "$glibc_version" ge 2.31; then
  fail "当前系统版本不兼容。" "glibc_check_failed version=${glibc_version:-unknown}"
fi

missing=()
while IFS= read -r dependency; do
  [[ -z "$dependency" ]] && continue
  dpkg-query -W -f='${Status}' "$dependency" 2>/dev/null | grep -q 'install ok installed' \
    || missing+=("$dependency")
done < <(dpkg-deb -f "$package" Depends | tr ',' '\n' | sed 's/^ *//;s/ *$//')
if (( ${#missing[@]} > 0 )); then
  fail "电脑缺少必要的系统组件，本次未安装。" "missing_dependencies=${missing[*]}"
fi

printf '%s\n' "install_started" > "$result_file" 2>/dev/null || true
if ! pkexec /usr/bin/dpkg -i "$package" >> "$result_file" 2>&1; then
  fail "安装未完成。如果刚才点了取消，可以再次双击安装。" "$(tail -n 30 "$result_file" 2>/dev/null)"
fi

printf '%s\n' "install_success" > "$result_file" 2>/dev/null || true
show_message info "安装完成，文澜资料库即将启动。\n\n以后可从桌面左下角的应用菜单中打开。"
nohup /opt/wordvault/WordVault >/dev/null 2>&1 &
