"""Generate a LacTiC analysis report from the current database.

    python scripts/run_analysis.py                 # print + write reports/lactic_analysis.md
    python scripts/run_analysis.py --no-write       # print only

The report auto-detects whether the DB holds synthetic seed data (HS marks with
source='synthetic') and labels itself accordingly so demo numbers are never
mistaken for real findings.
"""
from __future__ import annotations

import argparse
import datetime as dt
import warnings
from io import StringIO

import _bootstrap  # noqa: F401

warnings.simplefilter("ignore")

from d3xc import config
from d3xc.analyze.metrics import load_frames
from d3xc.lactic import programs as P
from d3xc.lactic import projection as J
from d3xc.lactic import ratings as R


def _is_synthetic(frames) -> bool:
    hs = frames.get("hs")
    return hs is not None and not hs.empty and (hs["source"] == "synthetic").any()


def _md_table(df, cols, n=15, floatfmt=2):
    df = df[cols].head(n).copy()
    for c in cols:
        if df[c].dtype.kind == "f":
            df[c] = df[c].round(floatfmt)
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    lines = [header, sep]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines)


def build_report() -> str:
    frames = load_frames()
    out = StringIO()
    w = lambda *a: print(*a, file=out)  # noqa: E731

    synthetic = _is_synthetic(frames)
    w("# LacTiC Analysis — NCAA D3 Ohio Cross Country")
    w(f"_Generated {dt.datetime.now():%Y-%m-%d %H:%M} · seasons "
      f"{config.FIRST_SEASON}–{config.LAST_SEASON} · Region VI (Great Lakes)_")
    w()
    if synthetic:
        w("> ⚠️ **DEMO DATA.** This report was built on synthetic seed data "
          "(`scripts/seed_sample.py`). Numbers illustrate methodology only. Run a "
          "real TFRRS scrape to produce genuine findings.")
        w()

    r = frames["results"]
    w("## Dataset")
    w(f"- Teams: **{frames['teams'].shape[0]}**  ·  Athletes: "
      f"**{frames['athletes'].shape[0]}**  ·  Race results: **{len(r):,}**")
    w(f"- Team placements: **{len(frames['placements']):,}**  ·  "
      f"HS marks linked: **{len(frames['hs']):,}**  ·  "
      f"Coach tenures: **{len(frames['coaches'])}**")
    w()

    ar = R.compute_athlete_ratings(r)
    career = R.compute_career_ratings(r)
    strength = P.program_strength(ar)
    tiers = P.program_tiers(strength)

    for gender in ("men", "women"):
        w(f"## {gender.title()}")
        car_g = career[career["gender"] == gender]
        if not car_g.empty:
            w("### Top runners — career (meet-adjusted)")
            w(_md_table(car_g.sort_values("rating", ascending=False),
                        ["athlete_name", "team", "adj_pace_sec_per_km", "rating",
                         "races"], n=15))
            w()
        latest = int(strength[strength["gender"] == gender]["season"].max()) \
            if not strength[strength["gender"] == gender].empty else None
        if latest is not None:
            rank = P.rank_programs(strength[strength["gender"] == gender], gender, latest)
            w(f"### Program ranking — {latest}")
            w(_md_table(rank, ["rank", "team", "conference", "program_adj_pace",
                               "program_rating"], n=25))
            w()
        tg = tiers[tiers["gender"] == gender]
        if not tg.empty:
            w("### Program tiers (strength × trajectory)")
            w(_md_table(tg.sort_values(["tier", "latest_rating"],
                                       ascending=[True, False]),
                        ["team", "tier_label", "trend", "latest_rating",
                         "improvement_rate"], n=25, floatfmt=3))
            w()

    w("## Development model — most improved vs expected")
    res = J.run_projection()
    if res.n_samples:
        w(f"- Transitions modeled: **{res.n_samples:,}**  ·  CV MAE: "
          f"**{res.cv_mae:.3f}** sec/km  ·  persistence baseline: "
          f"**{res.baseline_mae:.3f}**  ·  skill vs baseline: "
          f"**{res.skill_vs_baseline*100:.0f}%**")
        w(f"- Top feature importances: " + ", ".join(
            f"`{k}` {v:.2f}" for k, v in list(res.importances.items())[:4]))
        w()
        ou = res.over_under.copy()
        ou["beat_projection_by"] = (-ou["residual"]).round(2)
        w("### Overperformers (ran faster than projected)")
        w(_md_table(ou, ["athlete_name", "team", "gender", "from_season",
                         "to_season", "beat_projection_by"], n=15))
        w()
        if not res.projections.empty:
            w("### Projected top improvers (returning athletes, next season)")
            w(_md_table(res.projections, ["athlete_name", "team", "gender",
                        "prev_adj_pace", "projected_pace", "projected_improvement"],
                        n=15))
            w()
    else:
        w("_Not enough season-to-season data to fit the development model._")
        w()

    w("## Methodology")
    w("- **Runner rating**: ridge two-way model `pace ~ athlete + meet` per "
      "gender/season; reported as neutral-course adjusted pace and a 0-100 rating.")
    w("- **Program rating**: mean adjusted pace of the top-5 runners; trajectory "
      "= OLS slope over seasons; tiers via KMeans on (strength, trajectory).")
    w("- **Development model**: GradientBoostingRegressor projecting next-season "
      "pace; residuals are out-of-fold to avoid leakage.")
    return out.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-write", action="store_true", help="print only")
    args = ap.parse_args()

    report = build_report()
    print(report)
    if not args.no_write:
        path = config.PROJECT_ROOT / "reports" / "lactic_analysis.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
        print(f"\n[written] {path}")


if __name__ == "__main__":
    main()
