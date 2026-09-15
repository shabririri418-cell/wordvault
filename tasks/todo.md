# Task List

## Phase 1: app-foundation

- [x] Task 1: 建立Python工程、测试和静态检查入口
  - Acceptance: 应用包可导入；测试和Ruff命令可执行。
  - Verify: `python -m pytest`; `python -m ruff check .`
  - Files: `pyproject.toml`, `src/wordvault/__init__.py`, `src/wordvault/__main__.py`, `tests/test_smoke.py`
- [x] Task 2: 实现资料库初始化和SQLite模式版本
  - Acceptance: 新目录可初始化，重复打开保持数据，非法目录返回明确错误。
  - Verify: `python -m pytest tests/integration/test_library_database.py`
  - Files: `src/wordvault/storage/database.py`, `tests/integration/test_library_database.py`
- [x] Task 3: 实现脱敏日志、轮转和诊断导出
  - Acceptance: 只接受白名单字段；敏感字段无法进入诊断包；支持清理。
  - Verify: `python -m pytest tests/unit/test_diagnostics.py`
  - Files: `src/wordvault/diagnostics/service.py`, `tests/unit/test_diagnostics.py`
- [x] Task 4: 实现首次运行和主窗口骨架
  - Acceptance: 可选择/打开资料库并显示环境状态。
  - Verify: GUI测试与手动启动。
  - Files: `src/wordvault/app.py`, `src/wordvault/ui/main_window.py`, `tests/gui/test_main_window.py`

## Checkpoint: Foundation

- [x] 全部测试和静态检查通过
- [x] 应用可启动且断网工作

## Phase 2: document-library

- [x] Task 5: 导入文件与文件夹、UUID存储及重复决策
- [x] Task 6: 文档列表、导出与调用WPS
- [x] Task 7: 内部回收站和外部变更一致性检查

## Phase 3: document-content

- [x] Task 8: `.docx`正文提取和解析失败隔离
- [x] Task 9: `.doc`适配器与WPS/本地工具回退
- [x] Task 10: 阅读预览、复制和来源引用

## Phase 4: classification

- [x] Task 11: 三级单一分类和未分类迁移
- [x] Task 12: 关键词与样本推荐、可信度和待复核

## Phase 5: full-text-search

- [x] Task 13: 文件名与正文索引、筛选和高亮
- [x] Task 14: 索引进度、暂停继续及重建

## Phase 6: offline-delivery

- [x] Task 15: 离线依赖缓存与AArch64 `.deb` 打包
- [ ] Task 16: 升级迁移回滚、验收资料和模拟文档集

## Checkpoint: Complete

- [x] 完整测试、静态检查和Windows开发构建通过
- [x] 核心用户流程通过
- [x] 脱敏诊断包通过负向泄密检查
- [ ] AArch64目标环境验收项记录完成
