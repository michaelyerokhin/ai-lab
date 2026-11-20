"""Let the tests import the week1 modules (client, triage, ...) from the parent folder."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
