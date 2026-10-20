import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "plugins" / "show-and-discuss" / "skills" / "present"
sys.path.insert(0, str(SKILL_DIR / "scripts"))
