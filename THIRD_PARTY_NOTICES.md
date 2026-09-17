# Third-party notices

WordVault is released under the MIT License. Its build and binary distributions
use third-party components under their own licenses.

| Component | Use | License |
|---|---|---|
| Python | Runtime | Python Software Foundation License |
| PySide6 / Qt for Python 6.8 | GUI runtime | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| Qt 6.8 libraries | GUI runtime | Primarily LGPL-3.0-only/GPL; individual modules may carry additional notices |
| PyInstaller | Binary packaging | GPL-2.0-or-later with the PyInstaller bootloader exception |
| SQLite | Local database and full-text search | Public domain |
| pytest | Test tooling only | MIT |
| pytest-qt | Test tooling only | MIT |
| Ruff | Development tooling only | MIT |
| docx (npm package) | Manual generation tooling only | MIT |
| Apache Tika (optional, not committed) | Legacy `.doc` text extraction | Apache-2.0 |

The Windows and Linux packages keep Qt/PySide shared libraries as replaceable
files alongside the application. Corresponding source is available from the
upstream projects and the exact versions are recorded in the requirements files.

- Qt for Python: <https://code.qt.io/cgit/pyside/pyside-setup.git/>
- Qt: <https://code.qt.io/cgit/qt/>
- PyInstaller: <https://github.com/pyinstaller/pyinstaller>
- Python: <https://github.com/python/cpython>
- Apache Tika: <https://tika.apache.org/>

This notice is informational and does not replace the license files shipped by
the respective upstream projects.
