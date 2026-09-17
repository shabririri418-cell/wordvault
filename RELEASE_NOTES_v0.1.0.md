# 文澜资料库 v0.1.0

首个公开测试版本，面向完全离线的 Word 文档整理、预览和全文搜索场景。

## 下载选择

- **Windows 10/11 x64**：下载 `WordVault-Windows-x64-preview-v0.1.0.zip`，解压后双击程序。
- **银河麒麟 V10 / 飞腾 ARM64**：下载 `WordVault-Kylin-ARM64-v0.1.0.tar.gz`，解压后双击安装图标。
- **Linux 管理员**：可直接下载 `wordvault_0.1.0_arm64.deb`。
- **操作与验收**：下载 `WordVault-User-and-Acceptance-Manual-zh-CN-v0.1.0.docx`。

## 主要功能

- `.doc` / `.docx` 文件和文件夹批量导入，原文件保留。
- 最多三级分类，一个文档归属一个分类。
- 文件名与正文全文搜索、筛选和搜索索引重建。
- 程序内正文预览、复制正文、复制并附来源。
- 调用本地 WPS 打开文档，并检测保存后的内容变化。
- 回收站、单份文档导出和分类批量导出。
- 完全离线运行；可导出不含正文、文件名和路径的脱敏诊断包。

## 验证情况

- Windows 自动化测试：70 项通过。
- ARM64 交叉/模拟环境测试：68 项通过，并完成程序自检。
- ARM64 主程序格式：ELF 64-bit AArch64。
- ARM64 构建基线：Debian 11 / glibc 2.31。

## 已知限制

- Windows 版本目前是预览测试版。
- ARM64 包尚需在实际银河麒麟和飞腾设备上完成最终兼容性验收。
- 旧版 `.doc` 正文提取需要本机可用的 Apache Tika、`antiword` 或 `catdoc`；缺少解析器时不影响其他文档。
- 程序不提供应用级加密和完整备份，数据保护依赖操作系统权限和用户备份策略。

## SHA-256

```text
008e56d5a8de007a71c1bd147768b448716cc12c971587b595e66ffd6f189860  WordVault-Windows-x64-preview-v0.1.0.zip
0c087674424745149456d241f593abd7e28d8f69100611d9121c993216c35b5d  WordVault-Kylin-ARM64-v0.1.0.tar.gz
e236d14cd5c2f3802e31727396830632f595632cac5c9fe839ca9f27b18ea01d  wordvault_0.1.0_arm64.deb
d3bb05818fbaf348bc1a57392ce4dc53015bcc7610a728bffbe428867e33690e  WordVault-User-and-Acceptance-Manual-zh-CN-v0.1.0.docx
```

报告问题时请勿上传真实业务文档、正文、文件名、文件路径、分类名称或敏感截图。
