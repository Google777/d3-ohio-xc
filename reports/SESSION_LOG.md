# D3 Ohio XC — Project Status & Session Log

_Durable summary of the build so work/context survives a session reset._

## What this is
A staged pipeline analyzing NCAA **Division III Ohio** cross country program
development (2016–2025; 2020 cancelled = COVID), from TFRRS scrape → SQLite →
analysis (LacTiC ratings + statistics) → Streamlit dashboard + Markdown/HTML reports.

## Data state (rebuilt deterministically from HTTP cache)
- **24 tracked programs**: all 10 OAC + full NCAC (Ohio: Denison, Hiram, Kenyon,
  Oberlin, Ohio Wesleyan, Wittenberg, Wooster; **non-Ohio NCAC added: Allegheny
  (2016–21, then left), DePauw, Wabash**) + HCAC (Bluffton, Defiance, Mount St.
  Joseph) + UAA (Case Western).
- **National context**: 219 non-Ohio teams tagged `tracked=False` (championship
  meets only) — excluded from all Ohio ratings/dev/coaching analyses via guards.
- ~26.5k individual results, ~2.1k team placements, 9 national championships.
- Athlete **origin** (hometown/HS/home_state) scraped from Sidearm roster pages
  for 15/16 sites (~1,600 hometowns). Coaches curated in `config/coaches.csv`.
- HS→college marks NOT available (Athletic.net 403-blocked); `config/hs_marks.csv`
  is a fillable curated stub.

## Canonical rebuild sequence (all from cache; fast)
1. `python scripts/rebuild_from_cache.py`   (parses every cached meet file; tracked teams + coaches + hs)
2. `python scripts/scrape_nationals.py`      (full national field, tracked=False)
3. `python scripts/scrape_origins.py --delay 0.0`  (roster origin)
Then: `python scripts/run_stats.py` (writes reports/statistics.{md,html}) and
`python scripts/school_report.py` (reports/school_timelines.{md,html}).

## Key modules
- scrape: `tfrrs.py` (team/athlete/meet parsers, classify_meet_kind, discovery),
  `rosters.py` (origin), `http.py` (polite cache), `timeutil.py` (Riegel + VDOT date).
- store: `db.py` (SQLAlchemy; Team.tracked flag), `loaders.py`.
- analyze: `metrics.py`, `development.py` (champ_season_best = Riegel+prefer-8k),
  `stats.py`, `coaching.py` (DiD + placebo), `national.py`, `thresholds.py`,
  `standardize.py` (VDOT + course adjustment).
- lactic: `ratings.py` (ridge meet-adjusted), `power.py` (PacePower EWMA — best
  individual predictor), `elo.py`, `validate.py`, `programs.py`, `projection.py`.
- dashboard: `dashboard/app.py` (views: LacTiC predictive, Statistics, Coaching &
  Dynamics, National, LacTiC Rankings, Team development, Most improved, Conference,
  Regional & National, HS→College).

## Headline validated findings
- **Predictive (out-of-sample, 2024–25 holdout):** PacePower (recency-weighted
  pace) best individual predictor **86.7%** pairwise > career-best 83% > Elo 79%.
  Team-placement prediction Spearman **0.88**.
- **Development effect** (Riegel + prefer-8k, controls for arrival caliber): men
  **Wilmington +19.4, John Carroll +16.3, Otterbein +16.2, Denison +13.4**.
  Descriptive, NOT validated; survivorship caveat.
- **Placement vs development**: placement is driven by ABSOLUTE top-5 (arrival −
  improvement); high-dev programs (Wilmington/Denison) recruit slow, so finish
  mid-pack. JCU wins by recruiting fast + developing; Case Western by recruiting
  (national reach) not developing.
- **Recruiting reach**: Oberlin 93% out-of-state (24 states), Kenyon 86%, Denison
  77%, CWRU 70% vs Mount Union 91% in-state, JCU 89%.
- **Coaching DiD + placebo (airtight)**: only **Kenyon women 2020 (Kissane)** is
  CREDIBLE (passes placebo). Kenyon men 2023 (Shellhouse) significant but placebo
  untestable. John Carroll/Fuelling 2024 flat (graduation confound removed) and
  its placebo is significant → causal read forbidden.
- **Tier bars (course+distance-neutral VDOT, connected circuit):** OAC is tougher
  to win than NCAC (men adjVDOT ~65.7 vs 63.5; women ~65.0 vs 61.9).
- **"Massive jump" DISPROVED**: course-adjusted winning bar is stable/slightly
  softer over rolling 5/3/1yr. Individuals/programs improve, but the *bar to win*
  doesn't move (relative standard). Raw-time jumps were course/distance artifacts.

## Standardization (VDOT) — status & caveats
- `standardize.py`: VDOT (Daniels-Gilbert) fixes varying distance; course
  adjustment via ridge `VDOT ~ athlete + meet` on the connected circuit.
- Reliable RELATIVE within the Ohio conference circuit. NOT reliable for the
  national meet (under-identified: national-only athletes + rotating venue).
- CALIBRATION in progress: anchor neutral reference to championship-type courses
  (not circuit mean, which includes fast flat 5k invites) so VDOT→5k is literal.

## Tests: 59 passing (pytest). Dashboard views smoke-tested in isolated
subprocesses (Streamlit AppTest SIGSEGVs with multiple instances per process).

## Honest data limits
- 2020 season absent (COVID) — correct, not a gap.
- HS times unavailable (Athletic.net blocked) — HS→college jump needs curation.
- National teams: context only (championship meets), not full histories.
- Non-Ohio NCAC (Allegheny/DePauw/Wabash) coverage limited to cached shared meets.

## Immediate next steps
1. VDOT calibration to championship-course reference + integrate tier bars onto
   adjVDOT; add `Standardized (VDOT)` dashboard view + tests. (IN PROGRESS)
2. Optional: HS curation; stage-matched coaching controls; promote national teams
   to rating competitors ("national LacTiC").
