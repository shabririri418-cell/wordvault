# 文澜资料库（WordVault）

一款完全离线的 Word 文档分类、预览与全文搜索工具。支持 Windows 预览版，
以及银河麒麟 V10、飞腾 D2000/8（AArch64）和 WPS 环境。

程序不包含网络请求、遥测、云端模型或在线更新。文档、索引、分类和诊断信息
全部保存在用户选择的本地资料库中。

## 下载

请从 GitHub Releases 下载：

- `文澜资料库-Windows预览测试包.zip`：Windows 10/11 x64 预览测试版。
- `文澜资料库-银河麒麟ARM64-双击安装.tar.gz`：银河麒麟 ARM64 一键安装包。
- `wordvault_0.1.0_arm64.deb`：提供给 Linux 管理员的原始 Debian 安装包。
- `文澜资料库-操作与功能测试手册.docx`：安装、操作和现场验收手册。

> ARM64 包通过 Debian 11/glibc 2.31 基线和 QEMU AArch64 环境构建验证，
> 仍建议在实际银河麒麟设备上完成最终验收。Windows 包为预览测试版。

## 当前能力

- 将 `.doc/.docx` 复制到程序管理的资料库，支持递归导入。
- 检测同名或相同内容，并提供覆盖、保留两份或取消。
- `.docx` 正文提取、阅读预览、正文复制和中文全文搜索。
- 最多三级、单一归属分类，以及关键词/人工样本离线推荐。
- 文档导出、内部回收站和资料库一致性检测服务。
- 本地 WPS 打开、脱敏诊断日志和环境检测。
- 不含网络请求、遥测、云端模型或在线更新。

旧 `.doc` 优先使用随安装包审核交付的 Apache Tika 本地解析器，也可回退到目标系统已有的 `antiword` 或 `catdoc`。WPS没有稳定公开的离线无界面转换接口，因此不使用云端WPS转换服务；最终兼容性需在客户银河麒麟环境完成第二阶段验证。

## 从源码运行

```powershell
python -m pip install -r requirements-dev.txt
$env:PYTHONPATH="src"
python -m wordvault
```

需要 Python 3.11 或更高版本。图形界面依赖 PySide6。

## 验证

```powershell
$env:QT_QPA_PLATFORM="offscreen"
python -m pytest -q
python -m ruff check .
```

项目包含单元测试、集成测试、GUI 测试、性能测试和安装包测试。`acceptance/samples`
中的 64 份 Word 文档均为自动生成的虚构材料，不含真实业务数据。

## AArch64 离线构建

推荐在银河麒麟或兼容的 AArch64 Linux 构建机上执行：

```bash
python3 -m pip download --dest vendor/wheels -r requirements-build.txt
./packaging/build-deb.sh
```

客户电脑只接收生成的 `.deb`，不需要联网安装 Python 包。

没有 ARM64 电脑时，可在已启动 Docker Desktop 的 Windows 电脑上通过 QEMU 模拟构建：

```powershell
./packaging/build-arm64-docker.ps1
```

安装包输出到 `dist/arm64`。该流程使用 Debian 11/glibc 2.31 基线和 PySide6 6.8，
用于降低旧版银河麒麟的运行库兼容风险。Docker 模拟构建不能替代客户电脑上的最终确认。

客户可离线执行自检并生成脱敏诊断包：

```bash
/opt/wordvault/WordVault --self-check \
  --library-root /实际资料库目录 \
  --output wordvault-diagnostics.zip
```

## 隐私边界

可导出诊断信息不包含正文、文件名、文件路径、搜索词、分类名称或剪贴板内容。资料库不提供应用级加密和完整备份，安全及灾难恢复依赖客户的操作系统和存储策略。

## 参与开发

欢迎提交 Issue 和 Pull Request。报告问题时请勿上传真实业务文档、正文、文件名、
文件路径、分类名称或包含敏感内容的截图；请优先提供程序生成的脱敏诊断包。

## 许可证

项目源代码采用 [MIT License](LICENSE) 开源。运行时和构建工具的第三方许可见
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
