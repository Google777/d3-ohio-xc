"""Build a self-contained coach dashboard ZIP.

Bundles code + the prebuilt database + config + one-click launchers +
instructions, excluding the virtualenv, caches, git, and the large HTTP
cache. The coach unzips and double-clicks a launcher; it sets up a private
environment on first run and opens the dashboard in the browser.

    python scripts/make_package.py
-> dist/d3xc-coach-dashboard.zip
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP = "d3xc-coach-dashboard"          # top-level folder inside the zip
OUT = ROOT / "dist" / "d3xc-coach-dashboard.zip"

FILES = [
    "requirements.txt",
    "START_HERE.txt",
    "FEEDBACK.txt",
    "Start_Dashboard_Windows.bat",
    "Start_Dashboard_Mac.command",
    "Start_Dashboard_Linux.sh",
    "data/d3xc.db",
]
DIRS = ["src", "config"]              # config included for completeness
EXECUTABLE = {"Start_Dashboard_Mac.command", "Start_Dashboard_Linux.sh"}
SKIP_SUFFIX = (".pyc",)
SKIP_PART = ("__pycache__", ".ipynb_checkpoints")


def _add(zf: zipfile.ZipFile, src: Path, arc: str):
    data = src.read_bytes()
    info = zipfile.ZipInfo(f"{TOP}/{arc}")
    info.compress_type = zipfile.ZIP_DEFLATED
    # rwxr-xr-x for launchers, rw-r--r-- otherwise (so double-click works)
    mode = 0o755 if src.name in EXECUTABLE else 0o644
    info.external_attr = mode << 16
    zf.writestr(info, data)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(OUT, "w") as zf:
        for f in FILES:
            p = ROOT / f
            if not p.exists():
                raise SystemExit(f"missing required file: {f}")
            _add(zf, p, f)
            n += 1
        for d in DIRS:
            base = ROOT / d
            for p in sorted(base.rglob("*")):
                if p.is_dir():
                    continue
                if p.suffix in SKIP_SUFFIX or any(s in p.parts for s in SKIP_PART):
                    continue
                _add(zf, p, str(p.relative_to(ROOT)))
                n += 1
        # top-level coach one-pagers (any generated coach_report_*.html)
        for p in sorted((ROOT / "reports").glob("coach_report_*.html")):
            arc = p.stem.replace("coach_report_", "") + "_summary.html"
            _add(zf, p, arc)
            n += 1
    size = OUT.stat().st_size / 1e6
    print(f"[built] {OUT}  ({n} files, {size:.1f} MB)")


if __name__ == "__main__":
    main()
