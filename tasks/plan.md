# Implementation Plan: 离线涉密 Word 资料管理工具

## Overview

以 Python、PySide6 和 SQLite 构建中文离线桌面应用。先完成可运行基础和资料库闭环，再接入 Word 正文解析、分类、全文搜索，最后生成银河麒麟 AArch64 离线安装包。每个阶段保持可测试、可启动和可回滚。

## Architecture Decisions

- 采用分层单体应用：UI → 应用服务 → 领域模型 → SQLite/文件系统适配器。
- 资料文件用稳定 UUID 存储；原文件名、分类和状态保存在数据库。
- 所有文档解析器实现统一协议；`.docx` 使用原生解析器，`.doc` 允许接入本地工具或 WPS 适配器。
- 日志采用事件白名单，不允许业务层自由写入敏感字符串。
- 中文搜索先以 SQLite FTS5 能力为基础，通过自动化测试验证目标构建的分词效果。

## Build Order

1. `app-foundation`
2. `document-library`
3. `document-content`
4. `classification`
5. `full-text-search`
6. `offline-delivery`

## Verification Checkpoints

- Foundation：配置、数据库、日志测试通过，程序能启动。
- Library：真实临时目录完成导入、重复处理、回收站和导出闭环。
- Content：测试文档可提取、预览并生成引用，失败文档被隔离。
- Classification/Search：分类约束、推荐、全文检索和重建索引通过集成测试。
- Delivery：Windows开发构建通过；AArch64离线构建脚本和验收清单齐备。

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| 银河麒麟/WPS准确版本未知 | 高 | 环境检测、解析适配器、两轮客户兼容修复 |
| `.doc` 旧格式差异 | 高 | 多适配器回退并将单文件失败隔离 |
| PySide6 AArch64依赖可用性 | 高 | 在AArch64构建机锁定离线wheel；保留系统Qt适配路径 |
| 中文FTS相关度不理想 | 中 | 建立中文语料测试；必要时替换索引适配器 |
| 诊断日志泄密 | 高 | 白名单事件模型和负向泄密测试 |
| 无资料库备份 | 高 | 在UI及说明中明确风险；升级仅备份数据库 |

## Open Questions

- 银河麒麟、WPS的准确版本在客户首次环境检测后确定。
- `.deb` 最低系统依赖需在目标AArch64环境验证。

