"""Formal statistics report for D3 Ohio XC (2016-2025).

Writes reports/statistics.md and reports/statistics.html. Combines:
  * out-of-sample predictive validation of LacTiC (Elo + pace models)
  * program-development trends with significance
  * conference dynasties, competitive balance, the JCU->NCAC ripple
  * national appearances, athlete development
  * current predictive rankings (PacePower + Elo)

    python scripts/run_stats.py [--open]
"""
from __future__ import annotations

import argparse
import datetime as dt
import warnings
from io import StringIO

import _bootstrap  # noqa: F401

warnings.simplefilter("ignore")

import pandas as pd

from d3xc import config
from d3xc.analyze import stats as S
from d3xc.analyze import coaching as CO
from d3xc.analyze import national as NAT
from d3xc.analyze import standardize as SZ
from d3xc.analyze.metrics import load_frames
from d3xc.scrape.timeutil import seconds_to_time
from d3xc.lactic import elo as E
from d3xc.lactic import power as P
from d3xc.lactic import validate as V


def md_table(df, cols, n=12, r=3):
    df = df[cols].head(n).copy()
    for c in cols:
        if df[c].dtype.kind == "f":
            df[c] = df[c].round(r)
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = ["| " + " | ".join(str(v) for v in row) + " |"
            for _, row in df.iterrows()]
    return "\n".join([head, sep, *body])


def build(frames, history, out):
    w = lambda *a: print(*a, file=out)  # noqa: E731
    results, placements = frames["results"], frames["placements"]

    w("# LacTiC Statistics — NCAA D3 Ohio Cross Country")
    w(f"_Generated {dt.datetime.now():%Y-%m-%d} · seasons "
      f"{config.FIRST_SEASON}–{config.LAST_SEASON} (2020 cancelled, COVID) · "
      "all figures trace to TFRRS meet results_")
    w(f"\n- Race results: **{len(results):,}** · team placements: "
      f"**{len(placements):,}** · rated athletes: "
      f"**{results['athlete_id'].nunique():,}**\n")

    # ---- predictive validation ----
    w("## 1. Is LacTiC predictive? (out-of-sample)")
    w("Temporal holdout — models see only races *before* each test race.\n")
    acc = V.pairwise_accuracy(history, results, {2024, 2025})
    rows = [("Recency-weighted pace (PacePower)", acc["ewma_pace_accuracy"]),
            ("Blend: Elo + best pace", acc["blend_accuracy"]),
            ("Last-race pace", acc["last_pace_accuracy"]),
            ("Career-best pace (reactionary)", acc["prev_best_pace_accuracy"]),
            ("Meet-adjusted recency pace", acc["madj_ewma_accuracy"]),
            ("Head-to-head Elo", acc["pre_elo_accuracy"]),
            ("Coin flip", acc["coinflip"])]
    w(f"**Individual finish-order accuracy** (2024–25 holdout, {acc['races']} races):\n")
    w("| Predictor | Pairwise accuracy |")
    w("| --- | --- |")
    for name, v in rows:
        w(f"| {name} | {v*100:.1f}% |")
    tp = V.team_placement_prediction(history, placements, {2024, 2025})
    w(f"\n**Team-placement prediction** at 2024–25 championships "
      f"(pre-meet top-5 Elo → finish order): mean Spearman **{tp['mean_spearman']:.2f}** "
      f"(median {tp['median_spearman']:.2f}) across {tp['meets_evaluated']} meets.")
    w("\n> Takeaway: recency-weighted pace is the best individual predictor "
      "(~87%), clearly beating the career-best baseline and head-to-head Elo; "
      "Elo is strongest for **team** outcomes. LacTiC forecasts, it doesn't just "
      "restate results.\n")

    # ---- development trends ----
    traj = S.program_trajectories(frames)
    w("## 2. Program development (2016→2025, OLS w/ significance)")
    for g in ("men", "women"):
        t = traj[(traj.gender == g) & (traj.reg_p < 0.05)].sort_values("reg_slope_place_per_yr")
        risers = t[t.reg_slope_place_per_yr < 0]
        w(f"\n**{g.title()} — significant risers** (regional places gained/yr, p<0.05):")
        w(md_table(risers, ["team", "reg_slope_place_per_yr", "reg_r2", "reg_p"], 8))
        decl = t[t.reg_slope_place_per_yr > 0].sort_values("reg_slope_place_per_yr", ascending=False)
        if not decl.empty:
            w(f"\n**{g.title()} — significant declines:**")
            w(md_table(decl, ["team", "reg_slope_place_per_yr", "reg_r2", "reg_p"], 5))

    # ---- rolling trajectory ----
    w("\n### 3-year rolling trajectory (smooths the college-cycle swings)")
    w("Net change in the 3-yr rolling top-5 time (negative = improving) with raw "
      "year-to-year swing as a volatility check — big swings flag small/roster-"
      "sensitive programs whose single-season numbers over-read.\n")
    rc = S.rolling_change(frames, window=3)
    for g in ("men", "women"):
        rg = rc[rc.gender == g].sort_values("roll_time_change_s")
        w(f"\n**{g.title()} — steadiest improvers (3-yr smoothed):**")
        w(md_table(rg, ["team", "roll_time_change_s", "roll_regional_change",
                        "mean_yoy_swing_s"], 6, 1))
        sw = rg.sort_values("mean_yoy_swing_s", ascending=False)
        w(f"\n**{g.title()} — swingiest (largest avg year-to-year top-5 swing):**")
        w(md_table(sw, ["team", "mean_yoy_swing_s", "mean_yoy_swing_places"], 4, 1))

    # ---- dynasties ----
    w("\n## 3. Conference dynasties")
    tc = S.title_counts(placements)
    w("**Conference titles (men):**")
    w(md_table(tc[tc.gender == "men"], ["team", "titles"], 6))
    for conf in ("OAC", "NCAC"):
        ch = S.conference_champions(placements, conf)
        w(f"\n**{conf} men champions by year** "
          "(— = non-Ohio member won):")
        cm = ch[ch.gender == "men"][["season", "champion", "runner_up"]]
        cm = cm.fillna("—")
        w(md_table(cm, ["season", "champion", "runner_up"], 12))

    # ---- competitive balance ----
    w("\n## 4. Competitive balance")
    bt = S.balance_trend(frames)
    w("Trend of within-conference spread (SD of top-5 time); negative = "
      "teams converging. None are significant at p<0.05 over 9 seasons:\n")
    w(md_table(bt, ["conference", "gender", "sd_slope_s_per_yr", "r2", "p"], 8))

    # ---- JCU ripple ----
    w("\n## 5. The John Carroll → NCAC realignment (2025)")
    rip = S.jcu_ncac_ripple(frames)
    oac = rip["oac_men_champions"]
    w("OAC men champions: " + ", ".join(f"{y}:{t}" for y, t in sorted(oac.items())))
    w("\nJCU won 4 straight OAC titles (2021–24), then the **2025 NCAC** title in "
      "its first year; **Otterbein reclaimed the OAC** once JCU left.")
    shift = pd.DataFrame(rip["ncac_men_shift_2025_vs_2021_24"]).dropna(subset=["delta_places"])
    w("\n**NCAC Ohio men — mean placement 2025 vs 2021–24** "
      "(+ = pushed down after JCU joined):")
    w(md_table(shift.sort_values("delta_places"), ["team", "pre_2021_24", "y2025", "delta_places"], 8))

    # ---- nationals ----
    w("\n## 6. National-championship appearances")
    w(md_table(S.national_appearances(placements),
               ["team", "gender", "appearances", "best_finish"], 10))

    # ---- athlete development ----
    ad = S.athlete_development(frames)
    w("\n## 7. Athlete development (≥2 seasons)")
    for g in ("men", "women"):
        x = ad[ad.gender == g]["improvement_s"]
        w(f"- **{g.title()}** ({len(x)} athletes): debut→career-best improves "
          f"mean **{x.mean():.0f}s**, median {x.median():.0f}s (std distance).")

    from d3xc.analyze import development as D
    w("\n### Year-over-year improvement by college year")
    ct = D.class_transition_stats(results)
    w(md_table(ct, ["gender", "transition", "n", "mean_improve_s", "median_improve_s"], 12, 1))
    w("\n### Program development effect (improvement beyond arrival caliber)")
    w("Regression controls for debut speed; positive = develops runners more "
      "than their arrival time predicts.\n")
    eff = D.program_development_effect(results)
    for g in ("men", "women"):
        e = eff[eff.gender == g]
        w(f"\n**{g.title()} — top developers:**")
        w(md_table(e, ["team", "athletes", "mean_improve_s", "dev_effect_s"], 6, 1))
    w("\n### Program development on a rolling basis (3-yr)")
    w("Net change in 3-yr rolling top-5 time (negative = program getting faster) "
      "with year-to-year volatility — the smoothed read of how a program is "
      "developing across recruiting cycles.\n")
    rc2 = S.rolling_change(frames, window=3)
    for g in ("men", "women"):
        rg = rc2[rc2.gender == g].sort_values("roll_time_change_s")
        w(f"\n**{g.title()} — steadiest smoothed improvement:**")
        w(md_table(rg, ["team", "roll_time_change_s", "roll_regional_change",
                        "mean_yoy_swing_s"], 6, 1))

    w("\n> HS→college jump: Athletic.net blocks automated access, so true HS "
      "marks are curated in `config/hs_marks.csv`; once populated, the HS→college "
      "pace improvement activates. 'Arrival caliber' above uses debut-season time "
      "as the proxy baseline.")

    # ---- current predictive rankings ----
    w("\n## 8. Current predictive rankings (PacePower)")
    for g in ("men", "women"):
        top = P.top_predicted(results, g, 10)
        w(f"\n**{g.title()} — top predicted (projected championship time):**")
        w(md_table(top, ["athlete_name", "team", "proj_time", "races"], 10))
    w("\n**Predicted team strength (men, top-5 projected avg):**")
    w(md_table(P.team_pace_power(results).query("gender=='men'"),
               ["team", "team_proj_time"], 8))
    w("\n**Rolling-smoothed team projection (men, 3-yr form of top-5):** "
      "dampens one-off seasons, aligned with the college cycle.")
    w(md_table(P.rolling_team_projection(results, window=3).query("gender=='men'"),
               ["team", "team_roll_time"], 8))

    # ---- recruiting reach ----
    w("\n## 9. Recruiting reach & athlete origin")
    rr = S.recruiting_reach(frames)
    if not rr.empty:
        w("From roster hometowns (Sidearm sites). % out-of-state = how national a "
          "program's recruiting is. Coverage is partial (origin known for a "
          "subset of athletes).\n")
        for g in ("men", "women"):
            rg = rr[rr.gender == g].sort_values("pct_out_of_state", ascending=False)
            w(f"\n**{g.title()} — most national rosters:**")
            w(md_table(rg, ["team", "athletes_with_origin", "pct_out_of_state", "n_states"], 6, 1))
        dbo = S.development_by_origin(frames)
        if not dbo.empty:
            w("\n**Development by origin** (in-state vs out-of-state; debut & "
              "improvement in std-distance seconds):")
            w(md_table(dbo, ["gender", "origin", "athletes", "mean_debut_s", "mean_improve_s"], 8, 1))
    else:
        w("_Origin not yet scraped — run `python scripts/scrape_origins.py`._")

    # ---- dynamics & coaching ----
    w("\n## 10. Dynamics & coaching impact")
    w("_Descriptive & correlational — confounded by graduation cohorts, small "
      "rosters, the 2020 gap, and 2024 changes being too recent to read._\n")
    acc = CO.multiwindow_acceleration(frames)
    for g in ("men", "women"):
        ag = acc[acc.gender == g].sort_values("rate_5yr")
        w(f"\n**{g.title()} — improvement rate by trailing window** "
          "(s/yr in top-5 time; negative = getting faster) + 2yr‑vs‑10yr acceleration:")
        w(md_table(ag, ["team", "rate_10yr", "rate_5yr", "rate_2yr", "accel_2v10"], 8, 1))
    w("\n> Read the **5‑yr** rate as the stable trend; 1–2‑yr swings are "
      "dominated by graduating classes (small programs move wildly).")

    did = CO.coaching_change_did(frames, k=3, min_group=5)
    w("\n### Coaching-change effect — within-athlete DiD + placebo pre-trend test (airtight)")
    w("**Treated** = returners racing before *and* after the change; **control** = "
      "returners at programs with no change over the same years. **DiD<0** = the "
      "coach's returners improved more than comparable runners elsewhere. The "
      "**placebo** re-runs the DiD on a fake change `k` years earlier (both windows "
      "pre-treatment): a null placebo supports parallel trends (**CREDIBLE**); a "
      "significant placebo means a pre-existing trend (**SUSPECT**). 90% bootstrap CI.\n")
    suf = did[did.sufficient]
    w(md_table(suf, ["team", "gender", "change_year", "new_coach", "n_treated",
                     "did_s", "ci_lo", "ci_hi", "placebo_did_s", "verdict"], 20, 1))
    w("\n> **After the placebo gate, exactly one change is fully credible: "
      "Kenyon women 2020 (Kissane), DiD −113s, placebo −18 (n.s.).** Kenyon men "
      "2023 (Shellhouse, −32s) is significant but the placebo is untestable "
      "(insufficient pre-2020 history). Crucially the placebo **disqualifies** "
      "several naive stories: John Carroll (Fuelling) shows a *significant placebo* "
      "(−62s) — the program was already on a strong pre-trend that then flattened, "
      "so its ~0 real DiD must not be read as a coaching effect; same for Ohio "
      "Wesleyan 2023. This is the guardrail that will matter at national scale.")
    w("\n_Assumptions: parallel trends (now tested via placebo) and comparable "
      "career-stage mix; control is pooled stable-coach programs. Raw before/after "
      "+ recruiting shifts remain in the dashboard for context, not causal use._")

    # ---- national context ----
    w("\n## 11. National context — NCAA DIII Championships")
    w("The full 32‑team national field is ingested as **context only** "
      "(national teams tagged `tracked=False`; they never enter the Ohio "
      "ratings/development/coaching analyses). 2020 cancelled.\n")
    oa = NAT.ohio_at_nationals(frames)
    for g in ("men", "women"):
        og = oa[oa.gender == g].copy()
        og["best_ohio_place"] = og["best_ohio_place"].astype("Int64")
        w(f"\n**{g.title()} — Ohio at nationals vs the field:**")
        w(md_table(og, ["season", "ohio_qualifiers", "best_ohio_team",
                        "best_ohio_place", "national_champion"], 12, 0))
    aac = NAT.ohio_all_american_counts(frames)
    w("\n**Ohio All-Americans (top‑40 individuals at nationals) by program:**")
    w(md_table(aac, ["team", "gender", "all_americans"], 12, 0))
    w("\n> Best Ohio showings of the decade: **John Carroll men 4th (2021 & 2022)**; "
      "national titles went to North Central (Ill.), Pomona‑Pitzer, MIT, and "
      "Wis.‑La Crosse. John Carroll leads Ohio with 6 men's All‑Americans.")

    w("\n## 12. Standardized tiers — course- & distance-neutral VDOT (relative index)")
    w("XC times are confounded by course/terrain/conditions and varying length. "
      "We convert every performance to **VDOT** (fixes distance) and course-adjust "
      "via a meet-difficulty model. **Use adjVDOT as a RELATIVE index**: the "
      "meet coefficients absorb more than pure course, so the absolute VDOT→5k "
      "equivalents below are *indicative only, not calibrated PRs*. Reliable "
      "within the connected conference circuit; the national meet is "
      "under-identified on this scale (use finish place there).\n")
    vt = SZ.vdot_tier_summary(frames)
    if not vt.empty:
        vt = vt.copy()
        vt["equiv_5k_indicative"] = vt["equiv_5k_s"].map(seconds_to_time)
        for g in ("men", "women"):
            gg = vt[vt.gender == g]
            w(f"\n**{g.title()} — team top-5 to win (relative adjVDOT; higher = fitter):**")
            w(md_table(gg, ["tier", "median_vdot", "equiv_5k_indicative", "years"], 6, 1))
    w("\n> The clean, trustworthy read is **relative**: the **OAC is a tougher "
      "conference to win than the NCAC** on a course/distance-neutral basis (both "
      "genders), and rolling 5/3/1-yr the winning bar is **stable to slightly "
      "softer** — so the raw-time 'jump' was course/distance artifact, not a real "
      "rise in the bar to win. Absolute VDOT/5k values are approximate pending "
      "further calibration.")

    w("\n---\n### Methodology")
    w("- **PacePower**: recency-weighted (EWMA span 3) pace per athlete; "
      "predicts next-race pace, projected to 8k (men)/6k (women).")
    w("- **Elo**: chronological head-to-head, updated per race; team strength = "
      "top-5 mean. Used for team-placement forecasting.")
    w("- **Validation**: temporal holdout; pairwise finish-order concordance and "
      "Spearman rank correlation, all out-of-sample.")


def _html(md_text: str) -> str:
    # minimal markdown->html (headings, tables, lists, bold)
    import html as _h
    import re
    lines = md_text.split("\n")
    out, in_tbl = [], False
    for ln in lines:
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if not in_tbl:
                out.append("<table>")
                in_tbl = True
                tag = "th"
            else:
                tag = "td"
            out.append("<tr>" + "".join(f"<{tag}>{_h.escape(c)}</{tag}>" for c in cells) + "</tr>")
            continue
        if in_tbl:
            out.append("</table>")
            in_tbl = False
        ln2 = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _h.escape(ln))
        if ln.startswith("# "):
            out.append(f"<h1>{ln2[2:]}</h1>")
        elif ln.startswith("## "):
            out.append(f"<h2>{ln2[3:]}</h2>")
        elif ln.startswith("### "):
            out.append(f"<h3>{ln2[4:]}</h3>")
        elif ln.startswith("> "):
            out.append(f"<blockquote>{ln2[2:]}</blockquote>")
        elif ln.startswith("- "):
            out.append(f"<li>{ln2[2:]}</li>")
        elif ln.strip():
            out.append(f"<p>{ln2}</p>")
    if in_tbl:
        out.append("</table>")
    css = ("body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:900px;"
           "margin:0 auto;padding:24px;color:#1c2230}h1{color:#0f2a4a}h2{color:#0f2a4a;"
           "border-bottom:2px solid #dfe3ea;padding-bottom:4px;margin-top:28px}"
           "table{border-collapse:collapse;margin:8px 0;font-size:13px;box-shadow:0 1px 2px rgba(0,0,0,.06)}"
           "th,td{border-bottom:1px solid #eef0f4;padding:5px 10px;text-align:right}"
           "th:first-child,td:first-child{text-align:left}th{background:#eef2f8}"
           "blockquote{background:#eef7ee;border-left:4px solid #4a9d5b;margin:10px 0;padding:8px 14px}"
           "li{margin:2px 0}")
    return f"<!doctype html><meta charset='utf-8'><style>{css}</style>" + "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true")
    args = ap.parse_args()
    frames = load_frames()
    history = E.compute_elo(frames["results"])
    buf = StringIO()
    build(frames, history, buf)
    md = buf.getvalue()
    d = config.PROJECT_ROOT / "reports"
    d.mkdir(exist_ok=True)
    (d / "statistics.md").write_text(md, encoding="utf-8")
    (d / "statistics.html").write_text(_html(md), encoding="utf-8")
    print(f"[written] {d/'statistics.md'}\n[written] {d/'statistics.html'}")
    if args.open:
        import subprocess
        subprocess.Popen(["setsid", "xdg-open", str(d / "statistics.html")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
