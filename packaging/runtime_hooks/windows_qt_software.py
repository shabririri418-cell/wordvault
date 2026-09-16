from __future__ import annotations

import os


# PyInstaller loads its PySide6 runtime hook before the application module. These
# values therefore have to be applied here, before Qt initializes its graphics stack.
os.environ["QT_OPENGL"] = "software"
os.environ["QT_QUICK_BACKEND"] = "software"
