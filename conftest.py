"""Pytest: Repo-Verzeichnis auf sys.path, damit die Tests flach importieren können."""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
