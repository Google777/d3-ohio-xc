"""Dashboard smoke test: every view must render without raising.

Streamlit's AppTest crashes (native SIGSEGV) when multiple app instances run in
one process, so each view is verified in its OWN subprocess. Skips if no DB has
been built yet (run scripts/seed_sample.py first).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from d3xc import config

pytestmark = pytest.mark.skipif(
    not config.DB_PATH.exists(),
    reason="no DB; run `python scripts/seed_sample.py` to enable dashboard tests",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIEWS = ["Coach Mode", "📖 How it works", "LacTiC (predictive)", "Statistics",
         "Coaching & Dynamics", "National", "Standardized (VDOT)", "Scenario",
         "LacTiC Rankings", "Team development", "Most improved", "Conference",
         "Regional & National", "HS → College"]

_RUNNER = """
import sys
from streamlit.testing.v1 import AppTest
view = sys.argv[1]
at = AppTest.from_file("src/d3xc/dashboard/app.py", default_timeout=60)
at.query_params["view"] = view
at.run()
assert not at.exception, [e.value for e in at.exception]
assert at.title[0].value.startswith("\U0001F3C3")
print("OK")
"""


@pytest.mark.parametrize("view", VIEWS)
def test_view_renders(view):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    proc = subprocess.run(
        [sys.executable, "-c", _RUNNER, view],
        cwd=PROJECT_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, f"view {view!r} failed:\n{proc.stdout}\n{proc.stderr}"
    assert "OK" in proc.stdout
