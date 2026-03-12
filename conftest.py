import os
import sys

ROOT = os.path.dirname(__file__)
SRC_DIR = os.path.join(ROOT, "src")

# Add src to sys.path early so tests can import `src.*`
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Also ensure PYTHONPATH contains src for subprocesses
os.environ.setdefault(
    "PYTHONPATH", SRC_DIR + os.pathsep + os.environ.get("PYTHONPATH", "")
)
