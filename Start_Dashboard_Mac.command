#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo "============================================"
echo "   D3 Ohio XC - Coach Dashboard"
echo "============================================"
echo "Starting up... (the FIRST launch takes a minute to set up; later launches are fast)"
echo

PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  for c in /usr/local/bin/python3 /opt/homebrew/bin/python3 \
           /Library/Frameworks/Python.framework/Versions/3.*/bin/python3; do
    [ -x "$c" ] && PY="$c" && break
  done
fi
if [ -z "$PY" ]; then
  echo "Python 3 was not found on this Mac."
  echo
  echo "   1) Install it from https://www.python.org/downloads/"
  echo "   2) If you JUST installed it, close this window and double-click again."
  echo
  read -n 1 -s -r -p "Press any key to close."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Creating a private environment for the app..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --disable-pip-version-check --quiet --upgrade pip
python -m pip install --disable-pip-version-check --quiet -r requirements.txt

echo
echo "Launching the dashboard in your web browser..."
echo "(To STOP the app later, just close this window.)"
echo
exec python -m streamlit run src/d3xc/dashboard/app.py
