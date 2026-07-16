from __future__ import annotations

import sys
from pathlib import Path


EXAMPLES = Path(__file__).parents[1] / "bloomberg-api" / "examples"
sys.path.insert(0, str(EXAMPLES))
