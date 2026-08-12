"""Comprehensive per-school, per-season, per-coach XC timeline report.

Built from concrete meet data (championship placements + real top-5 times), not
the ML ratings. Writes both Markdown and a styled, self-contained HTML page:

    python scripts/school_report.py            # writes reports/school_timelines.{md,html}
    python scripts/school_report.py --open      # ...and open the HTML in a browser
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import warnings

import _bootstrap  # noqa: F401

warnings.simplefilter("ignore")

from d3xc import config
from d3xc.analyze.metrics import load_frames, school_timeline
from d3xc.scrape.timeutil import seconds_to_time

GENDER_LABEL = {"men": "Men", "women": "Women"}


def _place(v) -> str:
    if v is None or (isinstance(v, float) and v != v):  # None or NaN
        return "—"
    n = int(v)
    suf = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _time(v) -> str:
    return seconds_to_time(v) if v is not None and v == v else "—"  # noqa: PLR0124


def _rowspan_coaches(df):
    """Yield (season, coach, conf, reg, nat, top5, spread, depth) display rows."""
    for _, r in df.iterrows():
        yield (
            int(r["season"]),
            r["coach"] or "—",
            _place(r["conf_place"]),
            _place(r["regional_place"]),
            _place(r["national_place"]),
            _time(r["top5_avg_seconds"]),
            (f"{r['spread_1_5']:.0f}s" if r["spread_1_5"] == r["spread_1_5"] else "—"),
            int(r["n_athletes"]),
        )


COLS = ["Season", "Head Coach", "Conf", "Great Lakes Reg.", "Nationals",
        "Top-5 Avg", "1–5 Spread", "Scorers"]


def build_markdown(tl) -> str:
    lines = ["# D3 Ohio XC — Program Timelines by School & Coach",
             f"_Generated {dt.datetime.now():%Y-%m-%d} · seasons "
             f"{config.FIRST_SEASON}–{config.LAST_SEASON} (2020 season cancelled — COVID)_",
             "",
             "Championship finishes + real top-5 scoring times from TFRRS meet "
             "results. **Head-coach column is sourced from `config/coaches.csv`** "
             "(coaching history is not on TFRRS); '—' means not yet filled in.", ""]
    known_coaches = tl["coach"].notna().any()
    if not known_coaches:
        lines.append("> ⚠️ No real coaching data loaded yet — every Head Coach "
                     "cell is '—'. Provide `config/coaches.csv` to populate.")
        lines.append("")
    for conf in sorted(tl["conference"].unique()):
        lines.append(f"## {conf}")
        teams = sorted(tl[tl["conference"] == conf]["team"].unique())
        for team in teams:
            lines.append(f"### {team}")
            for gender in ("men", "women"):
                g = tl[(tl["team"] == team) & (tl["gender"] == gender)].sort_values("season")
                if g.empty:
                    continue
                lines.append(f"**{GENDER_LABEL[gender]}**")
                lines.append("| " + " | ".join(COLS) + " |")
                lines.append("| " + " | ".join("---" for _ in COLS) + " |")
                for row in _rowspan_coaches(g):
                    lines.append("| " + " | ".join(str(x) for x in row) + " |")
                lines.append("")
    return "\n".join(lines)


def build_html(tl) -> str:
    css = """
    body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
      margin:0;background:#f6f7f9;color:#1c2230}
    header{background:#0f2a4a;color:#fff;padding:20px 28px}
    header h1{margin:0 0 4px;font-size:22px} header p{margin:0;opacity:.85;font-size:13px}
    .wrap{padding:20px 28px;max-width:1100px;margin:0 auto}
    .note{background:#fff7e6;border:1px solid #ffe1a8;padding:10px 14px;border-radius:8px;
      font-size:13px;margin:14px 0}
    h2{margin:26px 0 6px;border-bottom:2px solid #dfe3ea;padding-bottom:4px;color:#0f2a4a}
    h3{margin:18px 0 2px;color:#12305a}
    .g{font-weight:600;color:#5a6270;margin:8px 0 2px;font-size:13px;text-transform:uppercase;letter-spacing:.04em}
    table{border-collapse:collapse;width:100%;background:#fff;margin:4px 0 8px;
      box-shadow:0 1px 2px rgba(0,0,0,.06);border-radius:8px;overflow:hidden;font-size:13px}
    th,td{padding:6px 10px;text-align:center;border-bottom:1px solid #eef0f4}
    th{background:#eef2f8;color:#0f2a4a;font-weight:600}
    td:first-child,th:first-child{text-align:left;font-variant-numeric:tabular-nums}
    td:nth-child(2){text-align:left}
    tr:hover td{background:#f3f8ff}
    .champ{background:#e8f7ec!important;font-weight:600}  /* 1st place */
    .top3{background:#f0f6ff!important}
    .coach{color:#8a94a6;font-style:italic}
    """
    def cell(row):
        season, coach, conf, reg, nat, top5, spread, depth = row
        def cls(p):
            if p == "1st":
                return ' class="champ"'
            if p in ("2nd", "3rd"):
                return ' class="top3"'
            return ""
        coach_html = coach if coach != "—" else '<span class="coach">—</span>'
        return ("<tr>"
                f"<td>{season}</td><td>{coach_html}</td>"
                f"<td{cls(conf)}>{conf}</td><td{cls(reg)}>{reg}</td>"
                f"<td{cls(nat)}>{nat}</td><td>{top5}</td><td>{spread}</td>"
                f"<td>{depth}</td></tr>")

    parts = [f"<header><h1>D3 Ohio XC — Program Timelines by School &amp; Coach</h1>"
             f"<p>Seasons {config.FIRST_SEASON}–{config.LAST_SEASON} · 2020 cancelled (COVID) · "
             f"championship finishes + real top-5 times from TFRRS</p></header><div class='wrap'>"]
    if not tl["coach"].notna().any():
        parts.append("<div class='note'>⚠️ Head-coach column is empty — coaching "
                     "history isn't on TFRRS. Fill <code>config/coaches.csv</code> "
                     "(team, gender, coach, start_year, end_year) to populate it.</div>")
    header_cells = "".join(f"<th>{c}</th>" for c in COLS)
    for conf in sorted(tl["conference"].unique()):
        parts.append(f"<h2>{conf}</h2>")
        for team in sorted(tl[tl["conference"] == conf]["team"].unique()):
            parts.append(f"<h3>{team}</h3>")
            for gender in ("men", "women"):
                g = tl[(tl["team"] == team) & (tl["gender"] == gender)].sort_values("season")
                if g.empty:
                    continue
                parts.append(f"<div class='g'>{GENDER_LABEL[gender]}</div>")
                parts.append(f"<table><thead><tr>{header_cells}</tr></thead><tbody>")
                parts += [cell(r) for r in _rowspan_coaches(g)]
                parts.append("</tbody></table>")
    parts.append("</div>")
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            "<title>D3 Ohio XC — Program Timelines</title>"
            f"<style>{css}</style></head><body>{''.join(parts)}</body></html>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true", help="open the HTML in a browser")
    args = ap.parse_args()

    tl = school_timeline(load_frames())
    out_dir = config.PROJECT_ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "school_timelines.md"
    html_path = out_dir / "school_timelines.html"
    md_path.write_text(build_markdown(tl), encoding="utf-8")
    html_path.write_text(build_html(tl), encoding="utf-8")
    print(f"[written] {md_path}\n[written] {html_path}")
    print(f"rows: {len(tl)}  ·  schools: {tl['team'].nunique()}  ·  "
          f"coached rows: {int(tl['coach'].notna().sum())}")
    if args.open:
        subprocess.Popen(["setsid", "xdg-open", str(html_path)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"opening {html_path} ...")


if __name__ == "__main__":
    main()
