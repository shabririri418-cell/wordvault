# 能力地图：离线涉密 Word 资料管理工具

| 模块 ID | 职责 | 依赖 |
|---|---|---|
| `app-foundation` | ARM64 桌面程序框架、配置、资料库初始化、环境检测、脱敏日志 | — |
| `document-library` | 文件/文件夹导入、复制、重名处理、稳定编号、导出、回收站、外部变更检测 | `app-foundation` |
| `document-content` | `.doc/.docx` 正文提取、阅读型预览、复制引用、调用 WPS、解析失败隔离 | `document-library` |
| `classification` | 三级单一分类、未分类、关键词规则、样本学习、可信度及待复核 | `document-content` |
| `full-text-search` | 中文正文及文件名索引、相关度排序、高亮和筛选、索引重建 | `document-content`, `classification` |
| `offline-delivery` | ARM64 离线安装包、数据库升级回滚、诊断包导出及验收测试 | 前述全部模块 |

构建顺序：`app-foundation` → `document-library` → `document-content` → `classification` → `full-text-search` → `offline-delivery`

