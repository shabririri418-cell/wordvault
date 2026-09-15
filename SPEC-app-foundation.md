# Spec: app-foundation

## Objective

为个人用户建立一套完全离线的桌面应用基础，使后续文档库、正文解析、分类和搜索模块拥有稳定的本地运行环境。

目标平台为银河麒麟桌面操作系统、飞腾 Phytium D2000/8（AArch64）和 Linux 版 WPS。开发机可使用 Windows，但发布物必须在目标架构上重新构建并验证。

本模块交付以下能力：

1. 中文桌面主窗口和基础导航框架。
2. 首次运行选择资料库目录；已有资料库可重新打开。
3. SQLite 数据库初始化、模式版本记录和事务安全。
4. 系统、架构、WPS、磁盘空间和目录权限的本地环境检测。
5. 默认日志与临时详细诊断日志；所有字段经过白名单过滤。
6. 日志保留 30 天且总量不超过 100 MB。
7. 一键导出脱敏诊断包和一键清除日志。
8. 全部功能断网可用，不包含遥测、在线更新或外部 API 调用。

## Assumptions

1. 采用 Python 3.11+ 与 PySide6 构建桌面界面，以便在 Windows 开发、在 Linux AArch64 构建。
2. 使用 Python 标准库 `sqlite3`；运行时必须检测 SQLite 的 FTS5 能力，搜索模块不得静默假设其存在。
3. 最终安装包在银河麒麟 AArch64 构建环境生成，不从 Windows 交叉编译发布。
4. 安装由管理员完成，程序日常运行使用普通用户权限。
5. 资料库不做应用级加密；依赖操作系统账户与磁盘权限。
6. 第一版仅提供中文界面。
7. 客户具体银河麒麟和 WPS 版本未知，因此环境检测结果必须可进入脱敏诊断包。

## Tech Stack

- Python 3.11+
- PySide6 / Qt 6
- SQLite（Python 标准库）
- pytest、pytest-qt
- Ruff（格式与静态检查）
- PyInstaller（应用冻结）
- Debian `.deb` 打包脚本（AArch64 构建机执行）

依赖必须锁定版本并可提前下载到离线构建缓存。运行安装包不得访问网络。

## Commands

```powershell
# Windows 开发环境
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m wordvault
```

```bash
# 银河麒麟 AArch64 构建环境
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links vendor/wheels -r requirements-build.txt
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
./packaging/build-deb.sh
```

## Project Structure

```text
src/wordvault/              应用源代码
src/wordvault/app.py        应用入口和窗口生命周期
src/wordvault/config.py     非敏感应用配置
src/wordvault/storage/      SQLite 连接、事务和迁移
src/wordvault/diagnostics/  环境检测、日志和诊断包
src/wordvault/ui/           PySide6 界面
tests/unit/                 无外部 I/O 的单元测试
tests/integration/          临时目录和真实 SQLite 集成测试
tests/gui/                  Qt 组件测试
packaging/                  AArch64 离线构建和 `.deb` 打包
vendor/wheels/              离线依赖缓存，不提交二进制到源码仓库
tasks/                      实施计划及任务清单
```

## Code Style

使用类型标注、小而明确的服务对象和依赖注入；业务代码不直接读取全局路径。

```python
from pathlib import Path


class LibraryInitializer:
    def initialize(self, root: Path) -> None:
        resolved = root.expanduser().resolve()
        if not resolved.is_dir():
            raise ValueError("资料库目录不存在")
```

- 文件、函数和变量使用 `snake_case`，类使用 `PascalCase`。
- 面向用户的文字使用简体中文；内部标识和代码使用英文。
- 路径一律使用 `pathlib.Path`，不得手工拼接路径分隔符。
- 日志使用结构化事件编号，不拼接用户数据生成日志消息。

## Testing Strategy

- 单元测试覆盖配置校验、日志脱敏、容量轮转和环境结果规范化。
- 集成测试使用临时目录和真实 SQLite，验证首次初始化、重复打开、迁移失败回滚和目录不可写处理。
- GUI 测试验证首次运行选择目录、主窗口启动和诊断导出确认页。
- 网络隔离测试扫描源代码和运行配置，确保不存在业务网络端点。
- 所有行为遵循 RED → GREEN → REFACTOR；完整测试和静态检查通过后才进入下一增量。

## Boundaries

### Always

- 文件系统变更前解析并校验绝对目标路径。
- 数据库写操作使用事务。
- 诊断字段使用明确白名单，未知字段拒绝导出。
- 日志不得包含文件名、文件路径、正文、搜索词、分类名称、剪贴板或预览内容。
- 单个检测项失败时返回明确状态，不使整个程序退出。

### Ask first

- 增加需要联网才能运行的依赖。
- 改变资料库数据结构中已发布字段的含义。
- 更换 GUI 框架或数据库。
- 在安装包中加入 GPL 组件。

### Never

- 上传遥测、错误报告或客户资料。
- 在日志中记录任意未脱敏异常参数或原始堆栈局部变量。
- 以管理员权限运行日常应用。
- 将数据库或资料库默认放入程序安装目录。
- 在迁移失败时删除旧数据库。

## Success Criteria

1. 在无网络环境下可首次启动并选择一个可写资料库目录。
2. 程序创建数据库及版本信息；重复打开不会破坏已有状态。
3. 无权限、空间不足或数据库损坏时显示中文错误，不崩溃且不泄露路径到可导出日志。
4. 环境检测能报告操作系统版本、内核、AArch64 架构、WPS 状态、SQLite/FTS5 状态、磁盘空间和目录写入权限。
5. 默认日志超过 30 天或总量超过 100 MB 后按规则清理。
6. 导出的诊断包仅包含白名单环境字段、匿名事件、错误码、版本和耗时。
7. 代码在 Windows 开发环境测试通过，并具备在银河麒麟 AArch64 构建 `.deb` 的可执行入口。

## Open Questions

- 银河麒麟准确版本及包管理兼容性未知；在客户环境检测后确定 `.deb` 的最低系统依赖。
- WPS 准确版本和可执行文件路径未知；本模块只检测候选路径，调用与转换由 `document-content` 模块确定。
- 是否有可用的同配置非涉密测试机未知；目标平台最终验收依赖客户第二阶段反馈。

