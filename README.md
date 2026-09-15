# 文澜资料库

面向银河麒麟、飞腾 D2000/8（AArch64）和 WPS 的完全离线 Word 文档管理工具。

## 当前能力

- 将 `.doc/.docx` 复制到程序管理的资料库，支持递归导入。
- 检测同名或相同内容，并提供覆盖、保留两份或取消。
- `.docx` 正文提取、阅读预览、正文复制和中文全文搜索。
- 最多三级、单一归属分类，以及关键词/人工样本离线推荐。
- 文档导出、内部回收站和资料库一致性检测服务。
- 本地 WPS 打开、脱敏诊断日志和环境检测。
- 不含网络请求、遥测、云端模型或在线更新。

旧 `.doc` 优先使用随安装包审核交付的 Apache Tika 本地解析器，也可回退到目标系统已有的 `antiword` 或 `catdoc`。WPS没有稳定公开的离线无界面转换接口，因此不使用云端WPS转换服务；最终兼容性需在客户银河麒麟环境完成第二阶段验证。

## 开发运行

```powershell
python -m pip install -r requirements-dev.txt
$env:PYTHONPATH="src"
python -m wordvault
```

## 验证

```powershell
$env:QT_QPA_PLATFORM="offscreen"
python -m pytest -q
python -m ruff check .
```

## AArch64 离线构建

必须在银河麒麟或兼容的 AArch64 Linux 构建机上执行：

```bash
python3 -m pip download --dest vendor/wheels -r requirements-build.txt
./packaging/build-deb.sh
```

客户电脑只接收生成的 `.deb`，不需要联网安装 Python 包。

## 隐私边界

可导出诊断信息不包含正文、文件名、文件路径、搜索词、分类名称或剪贴板内容。资料库不提供应用级加密和完整备份，安全及灾难恢复依赖客户的操作系统和存储策略。
