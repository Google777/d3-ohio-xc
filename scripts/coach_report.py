"""Generate a plain-language coach one-pager (HTML) for one program.

    python scripts/coach_report.py "Kenyon" men "Kirk Shellhouse"

Writes reports/coach_report_<team>_<gender>.html — a single self-contained
page a coach can open in any browser (no server needed).
"""
from __future__ import annotations

import sys

from d3xc.analyze import project as PJ
from d3xc.analyze.metrics import load_frames

SPV, QUAL = 6.5, 67.1
QUAL_TIME = {"men": "25:27 for 8k", "women": "22:40 for 6k"}


def build(team: str, gender: str, prepared_for: str = "") -> str:
    f = load_frames()
    proj = PJ.project_teams(f, to_year=2029)
    row = proj[(proj.team == team) & (proj.gender == gender)].iloc[0]
    conf, cur_arr, cur = row["conference"], float(row["arrival_vdot"]), float(row["cur_vdot"])
    cc = (proj[(proj.conference == conf) & (proj.gender == gender)]
          .sort_values("cur_vdot", ascending=False).reset_index(drop=True))
    rank = int(cc.index[cc.team == team][0]) + 1
    others = cc[cc.team != team]["cur_vdot"]
    win_now = float(others.max()) if len(others) else cur
    act = PJ.coach_actions(f, team, gender, proj=proj, qualify=QUAL)
    tr, qr = act["title"][2029]["recruit"], act["qualify_recruit"]

    def sec(a, b):
        return f"{(a - b) * SPV:+.0f} sec/5k"

    def rec(v):
        return (f"recruit freshmen ~<b>{(v - cur_arr) * SPV:.0f} sec/5k faster</b>"
                if v else "needs a combined push")

    def dv(v):
        return (f"have runners improve ~<b>{v * SPV:.0f} sec/5k more each year</b>"
                if v else "needs a combined push")

    proj_cells = "".join(f"<td>{row[f'proj_{y}']:.1f}</td>" for y in range(2026, 2030))
    t29 = act["title"][2029]
    hdr = f"{team} {gender.title()}'s Cross Country — Program Outlook"
    sub = f"Prepared for {prepared_for}. " if prepared_for else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>{hdr}</title><style>
body{{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:760px;
margin:32px auto;color:#1a2230;line-height:1.5;padding:0 16px}}
h1{{font-size:22px;margin-bottom:2px}}h2{{font-size:16px;margin-top:26px;color:#2c5f8a}}
.sub{{color:#667;margin-top:0}}.badge{{background:#e8f5e9;border:1px solid #b7e0bb;
padding:8px 12px;border-radius:8px;font-size:14px}}
table{{border-collapse:collapse;margin:8px 0}}td,th{{border:1px solid #d5dbe4;
padding:6px 12px;text-align:center}}th{{background:#f4f7fb}}
.big{{font-size:15px}}.k{{color:#667}}.up{{color:#1a8a3a;font-weight:600}}
.dn{{color:#b23b3b;font-weight:600}}li{{margin:4px 0}}.foot{{color:#889;font-size:12px;margin-top:28px}}
</style></head><body>
<h1>{hdr}</h1><p class="sub">{sub}Course/distance-neutral fitness (VDOT); goals in real race times.</p>
<p class="badge">✔ Trust check: this model agreed with actual conference finishes
<b>90% of the time</b> (1,172 of 1,304 team head-to-head matchups, 2016–2025), and the
national-qualifying line checks out two independent ways.</p>

<h2>📍 Where you stand right now (2025)</h2>
<p class="big"><b>{conf} standing:</b> #{rank} of {len(cc)}
{'— you are the favorite.' if rank == 1 else f'(favorite: {cc.iloc[0].team}).'}</p>
<table><tr><th></th><th>Your team</th><th>To win {conf}</th><th>To qualify</th></tr>
<tr><th>Team fitness (VDOT)</th><td><b>{cur:.1f}</b></td>
<td>{win_now:.1f} <span class="{'up' if cur>=win_now else 'dn'}">({sec(cur,win_now)})</span></td>
<td>{QUAL:.1f} <span class="{'up' if cur>=QUAL else 'dn'}">({sec(cur,QUAL)})</span></td></tr></table>
<p class="big"><b>Incoming class:</b> {int(row['class_size'])} freshmen/yr, arriving at
<b>{cur_arr:.1f}</b> VDOT — to contend you'd recruit toward
<b>{tr:.1f}</b> (win {conf}) / <b>{qr:.1f}</b> (qualify).
Qualifying top-5 average ~<b>{QUAL_TIME[gender]}</b> at the regional.</p>

<h2>📈 If nothing changes (projection)</h2>
<table><tr><th>Season</th><th>2026</th><th>2027</th><th>2028</th><th>2029</th></tr>
<tr><th>Team fitness (VDOT)</th>{proj_cells}</tr></table>
<p class="k">This is your sustainable level at today's recruiting + training. The dip
reflects current seniors graduating faster than incoming classes replace them.</p>

<h2>🧭 What to do</h2>
<ul>
<li><b>Win the {conf} (by 2029, bar ≈ {t29['bar']:.1f}):</b> {rec(t29['recruit'])} —
<i>or</i> {dv(t29['develop'])}.</li>
<li><b>Qualify for nationals:</b> usually takes <b>both</b> — {rec(qr)} <b>and</b> keep
your runners improving each year.</li>
</ul>

<p class="foot">Early beta — numbers are a relative index (qualify bar cross-validated);
recruiting targets firm up once high-school times are added. Feedback welcome — just reply
to the email that sent you this.</p>
</body></html>"""


def main():
    team = sys.argv[1] if len(sys.argv) > 1 else "Kenyon"
    gender = sys.argv[2] if len(sys.argv) > 2 else "men"
    who = sys.argv[3] if len(sys.argv) > 3 else ""
    from d3xc import config
    out = config.PROJECT_ROOT / "reports" / f"coach_report_{team.replace(' ', '_')}_{gender}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(team, gender, who), encoding="utf-8")
    print(f"[written] {out}")


if __name__ == "__main__":
    main()
