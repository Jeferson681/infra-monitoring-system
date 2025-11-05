# conftest.py
# Configuração global para pytest: adiciona 'src' ao sys.path para permitir imports absolutos
import sys
from pathlib import Path

SRC_PATH = Path(__file__).parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))
