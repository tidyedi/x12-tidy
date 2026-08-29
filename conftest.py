import sys
from pathlib import Path

# Make the repo root importable so tests can reach scripts/.
sys.path.insert(0, str(Path(__file__).parent))
