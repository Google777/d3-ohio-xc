#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo "============================================"
echo "   D3 Ohio XC - Coach Dashboard"
echo "============================================"
echo "Starting up... (the FIRST launch takes a minute; later launches are fast)"
echo

PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "Python 3 was not found. Install it (e.g. 'sudo apt install python3 python3-venv')"
  echo "then run this file again."
  read -n 1 -s -r -p "Press any key to close."
  exit 1
fi

[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --disable-pip-version-check --quiet --upgrade pip
python -m pip install --disable-pip-version-check --quiet -r requirements.txt

echo
echo "Launching the dashboard in your web browser... (close this window to stop)"
echo
exec python -m streamlit run src/d3xc/dashboard/app.py
