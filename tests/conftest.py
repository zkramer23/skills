from __future__ import annotations

import sys
from pathlib import Path


EXAMPLES = Path(__file__).parents[1] / "bloomberg-api" / "examples"
PAYOFF_ENGINE = Path(__file__).parents[1] / "structured-note-payoff-engine" / "scripts"
METRIC_ORACLE = Path(__file__).parents[1] / "portfolio-analytics-qa" / "scripts"
NOTE_MONITOR = Path(__file__).parents[1] / "structured-note-monitor" / "scripts"
REPO_SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(EXAMPLES))
sys.path.insert(0, str(PAYOFF_ENGINE))
sys.path.insert(0, str(METRIC_ORACLE))
sys.path.insert(0, str(NOTE_MONITOR))
sys.path.insert(0, str(REPO_SCRIPTS))
