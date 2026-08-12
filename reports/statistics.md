# LacTiC Statistics — NCAA D3 Ohio Cross Country
_Generated 2026-08-09 · seasons 2016–2025 (2020 cancelled, COVID) · all figures trace to TFRRS meet results_

- Race results: **31,348** · team placements: **2,655** · rated athletes: **6,041**

## 1. Is LacTiC predictive? (out-of-sample)
Temporal holdout — models see only races *before* each test race.

**Individual finish-order accuracy** (2024–25 holdout, 145 races):

| Predictor | Pairwise accuracy |
| --- | --- |
| Recency-weighted pace (PacePower) | 86.7% |
| Blend: Elo + best pace | 84.5% |
| Last-race pace | 84.6% |
| Career-best pace (reactionary) | 83.0% |
| Meet-adjusted recency pace | 81.9% |
| Head-to-head Elo | 79.4% |
| Coin flip | 50.0% |

**Team-placement prediction** at 2024–25 championships (pre-meet top-5 Elo → finish order): mean Spearman **0.87** (median 0.89) across 12 meets.

> Takeaway: recency-weighted pace is the best individual predictor (~87%), clearly beating the career-best baseline and head-to-head Elo; Elo is strongest for **team** outcomes. LacTiC forecasts, it doesn't just restate results.

## 2. Program development (2016→2025, OLS w/ significance)

**Men — significant risers** (regional places gained/yr, p<0.05):
| team | reg_slope_place_per_yr | reg_r2 | reg_p |
| --- | --- | --- | --- |
| Wittenberg | -2.433 | 0.644 | 0.017 |
| Kenyon | -1.7 | 0.715 | 0.004 |
| Oberlin | -1.389 | 0.727 | 0.003 |
| John Carroll | -0.814 | 0.608 | 0.013 |

**Men — significant declines:**
| team | reg_slope_place_per_yr | reg_r2 | reg_p |
| --- | --- | --- | --- |
| Allegheny | 2.793 | 0.906 | 0.0 |
| Bluffton | 2.233 | 0.91 | 0.0 |
| Wabash | 1.538 | 0.599 | 0.014 |
| Ohio Wesleyan | 1.536 | 0.735 | 0.003 |
| DePauw | 1.422 | 0.566 | 0.019 |

**Women — significant risers** (regional places gained/yr, p<0.05):
| team | reg_slope_place_per_yr | reg_r2 | reg_p |
| --- | --- | --- | --- |
| Wittenberg | -2.095 | 0.597 | 0.015 |

**Women — significant declines:**
| team | reg_slope_place_per_yr | reg_r2 | reg_p |
| --- | --- | --- | --- |
| Bluffton | 2.373 | 0.753 | 0.011 |
| Oberlin | 2.015 | 0.826 | 0.001 |
| Allegheny | 1.777 | 0.591 | 0.016 |
| Kenyon | 1.538 | 0.63 | 0.011 |
| Heidelberg | 1.024 | 0.484 | 0.037 |

### 3-year rolling trajectory (smooths the college-cycle swings)
Net change in the 3-yr rolling top-5 time (negative = improving) with raw year-to-year swing as a volatility check — big swings flag small/roster-sensitive programs whose single-season numbers over-read.


**Men — steadiest improvers (3-yr smoothed):**
| team | roll_time_change_s | roll_regional_change | mean_yoy_swing_s |
| --- | --- | --- | --- |
| Marietta | -167.1 | 5.0 | 81.8 |
| Muskingum | -104.4 | -2.7 | 39.0 |
| Wilmington | -86.0 | -16.0 | 45.2 |
| Capital | -85.4 | -7.3 | 102.1 |
| Baldwin Wallace | -57.2 | -12.3 | 41.3 |
| Wittenberg | -55.3 | -17.0 | 42.7 |

**Men — swingiest (largest avg year-to-year top-5 swing):**
| team | mean_yoy_swing_s | mean_yoy_swing_places |
| --- | --- | --- |
| Defiance | 379.2 | nan |
| Capital | 102.1 | 7.2 |
| Marietta | 81.8 | 3.5 |
| Mount St. Joseph | 80.5 | 0.3 |

**Women — steadiest improvers (3-yr smoothed):**
| team | roll_time_change_s | roll_regional_change | mean_yoy_swing_s |
| --- | --- | --- | --- |
| Defiance | -375.8 | 0.0 | 238.6 |
| Mount St. Joseph | -291.5 | -2.0 | 103.3 |
| Marietta | -142.6 | 0.5 | 89.8 |
| Wilmington | -73.6 | 14.0 | 69.3 |
| Capital | -65.3 | 9.0 | 98.9 |
| Wittenberg | -59.2 | -13.0 | 44.7 |

**Women — swingiest (largest avg year-to-year top-5 swing):**
| team | mean_yoy_swing_s | mean_yoy_swing_places |
| --- | --- | --- |
| Defiance | 238.6 | nan |
| Mount St. Joseph | 103.3 | nan |
| Capital | 98.9 | 3.0 |
| Muskingum | 96.3 | 1.8 |

## 3. Conference dynasties
**Conference titles (men):**
| team | titles |
| --- | --- |
| John Carroll | 5 |
| DePauw | 4 |
| Otterbein | 3 |
| Oberlin | 2 |
| Ohio Northern | 2 |
| Allegheny | 1 |

**OAC men champions by year** (— = non-Ohio member won):
| season | champion | runner_up |
| --- | --- | --- |
| 2016 | Ohio Northern | Mount Union |
| 2017 | Ohio Northern | Mount Union |
| 2018 | Otterbein | John Carroll |
| 2019 | Otterbein | John Carroll |
| 2021 | John Carroll | Otterbein |
| 2022 | John Carroll | Otterbein |
| 2023 | John Carroll | Ohio Northern |
| 2024 | John Carroll | Mount Union |
| 2025 | Otterbein | Mount Union |

**NCAC men champions by year** (— = non-Ohio member won):
| season | champion | runner_up |
| --- | --- | --- |
| 2016 | Allegheny | DePauw |
| 2017 | DePauw | Allegheny |
| 2018 | DePauw | Allegheny |
| 2019 | DePauw | Wabash |
| 2021 | DePauw | Allegheny |
| 2022 | Oberlin | DePauw |
| 2023 | Wabash | Oberlin |
| 2024 | Oberlin | Wittenberg |
| 2025 | John Carroll | Kenyon |

## 4. Competitive balance
Trend of within-conference spread (SD of top-5 time); negative = teams converging. None are significant at p<0.05 over 9 seasons:

| conference | gender | sd_slope_s_per_yr | r2 | p |
| --- | --- | --- | --- | --- |
| HCAC | men | 13.589 | 0.132 | 0.549 |
| HCAC | women | -43.857 | 0.765 | 0.322 |
| NCAC | men | 2.11 | 0.09 | 0.433 |
| NCAC | women | -0.621 | 0.01 | 0.794 |
| OAC | men | -2.666 | 0.157 | 0.291 |
| OAC | women | 0.583 | 0.009 | 0.803 |

## 5. The John Carroll → NCAC realignment (2025)
OAC men champions: 2016:Ohio Northern, 2017:Ohio Northern, 2018:Otterbein, 2019:Otterbein, 2021:John Carroll, 2022:John Carroll, 2023:John Carroll, 2024:John Carroll, 2025:Otterbein

JCU won 4 straight OAC titles (2021–24), then the **2025 NCAC** title in its first year; **Otterbein reclaimed the OAC** once JCU left.

**NCAC Ohio men — mean placement 2025 vs 2021–24** (+ = pushed down after JCU joined):
| team | pre_2021_24 | y2025 | delta_places |
| --- | --- | --- | --- |
| Kenyon | 6.25 | 2.0 | -4.25 |
| Wabash | 4.25 | 4.0 | -0.25 |
| Oberlin | 2.25 | 3.0 | 0.75 |
| Denison | 4.75 | 6.0 | 1.25 |
| Wooster | 5.25 | 7.0 | 1.75 |
| Ohio Wesleyan | 7.25 | 9.0 | 1.75 |
| DePauw | 3.0 | 5.0 | 2.0 |
| Wittenberg | 4.75 | 8.0 | 3.25 |

## 6. National-championship appearances
| team | gender | appearances | best_finish |
| --- | --- | --- | --- |
| Carleton | women | 9 | 1.0 |
| Johns Hopkins | women | 9 | 1.0 |
| MIT | men | 9 | 1.0 |
| MIT | women | 9 | 1.0 |
| North Central (Ill.) | men | 9 | 1.0 |
| Pomona-Pitzer | men | 9 | 1.0 |
| Washington U. | women | 9 | 1.0 |
| Wis.-La Crosse | men | 9 | 1.0 |
| Claremont-Mudd-Scripps | women | 9 | 2.0 |
| SUNY Geneseo | men | 9 | 2.0 |

## 7. Athlete development (≥2 seasons)
- **Men** (953 athletes): debut→career-best improves mean **64s**, median 44s (std distance).
- **Women** (780 athletes): debut→career-best improves mean **57s**, median 36s (std distance).

### Year-over-year improvement by college year
| gender | transition | n | mean_improve_s | median_improve_s |
| --- | --- | --- | --- | --- |
| men | yr1→yr2 | 953 | 21.4 | 23.7 |
| men | yr2→yr3 | 564 | 14.1 | 21.8 |
| men | yr3→yr4 | 197 | -2.4 | 3.2 |
| men | yr4→yr5 | 4 | -51.2 | -5.1 |
| women | yr1→yr2 | 780 | 2.7 | 10.9 |
| women | yr2→yr3 | 447 | 12.5 | 21.6 |
| women | yr3→yr4 | 137 | -2.1 | 3.7 |
| women | yr4→yr5 | 4 | -52.0 | -28.1 |

### Program development effect (improvement beyond arrival caliber)
Regression controls for debut speed; positive = develops runners more than their arrival time predicts.


**Men — top developers:**
| team | athletes | mean_improve_s | dev_effect_s |
| --- | --- | --- | --- |
| Wilmington | 30 | 91.8 | 18.7 |
| John Carroll | 65 | 64.0 | 15.8 |
| Otterbein | 65 | 69.8 | 15.6 |
| Wabash | 42 | 79.8 | 14.6 |
| Denison | 39 | 76.7 | 12.8 |
| Heidelberg | 39 | 71.5 | 5.9 |

**Women — top developers:**
| team | athletes | mean_improve_s | dev_effect_s |
| --- | --- | --- | --- |
| Allegheny | 38 | 83.8 | 31.4 |
| John Carroll | 45 | 55.1 | 12.6 |
| DePauw | 46 | 68.6 | 12.2 |
| Oberlin | 53 | 69.8 | 11.3 |
| Ohio Wesleyan | 38 | 66.1 | 10.1 |
| Case Western Reserve | 46 | 57.2 | 9.1 |

### Program development on a rolling basis (3-yr)
Net change in 3-yr rolling top-5 time (negative = program getting faster) with year-to-year volatility — the smoothed read of how a program is developing across recruiting cycles.


**Men — steadiest smoothed improvement:**
| team | roll_time_change_s | roll_regional_change | mean_yoy_swing_s |
| --- | --- | --- | --- |
| Marietta | -167.1 | 5.0 | 81.8 |
| Muskingum | -104.4 | -2.7 | 39.0 |
| Wilmington | -86.0 | -16.0 | 45.2 |
| Capital | -85.4 | -7.3 | 102.1 |
| Baldwin Wallace | -57.2 | -12.3 | 41.3 |
| Wittenberg | -55.3 | -17.0 | 42.7 |

**Women — steadiest smoothed improvement:**
| team | roll_time_change_s | roll_regional_change | mean_yoy_swing_s |
| --- | --- | --- | --- |
| Defiance | -375.8 | 0.0 | 238.6 |
| Mount St. Joseph | -291.5 | -2.0 | 103.3 |
| Marietta | -142.6 | 0.5 | 89.8 |
| Wilmington | -73.6 | 14.0 | 69.3 |
| Capital | -65.3 | 9.0 | 98.9 |
| Wittenberg | -59.2 | -13.0 | 44.7 |

> HS→college jump: Athletic.net blocks automated access, so true HS marks are curated in `config/hs_marks.csv`; once populated, the HS→college pace improvement activates. 'Arrival caliber' above uses debut-season time as the proxy baseline.

## 8. Current predictive rankings (PacePower)

**Men — top predicted (projected championship time):**
| athlete_name | team | proj_time | races |
| --- | --- | --- | --- |
| Alex Phillip | John Carroll | 24:24.2 | 16 |
| Dan Cheung | Allegheny | 24:34.6 | 3 |
| Simon Heys | Wilmington | 24:34.8 | 25 |
| Jamie Dailey | John Carroll | 24:40.3 | 20 |
| Chase Hampton | Otterbein | 24:40.5 | 14 |
| Brayden Curnutt | Wabash | 24:43.0 | 13 |
| Noah Tobin | Wilmington | 24:49.1 | 28 |
| Dominic Patacsil | Wabash | 24:50.4 | 8 |
| Trey Razanauskas | Case Western Reserve | 24:52.0 | 16 |
| Ian McVey | Ohio Northern | 24:52.2 | 13 |

**Women — top predicted (projected championship time):**
| athlete_name | team | proj_time | races |
| --- | --- | --- | --- |
| Chip Smith | Capital | 18:39.8 | 1 |
| Mikey Arnone | Capital | 18:54.4 | 1 |
| Justin Rona | Capital | 18:59.9 | 1 |
| Kolin Brake | Capital | 19:01.3 | 1 |
| Braydon Nix | Capital | 19:36.4 | 1 |
| Charles Putnam | Marietta | 19:39.8 | 1 |
| Ridwan Aliawl | Capital | 19:49.2 | 1 |
| Kevin Hernandez | Marietta | 19:51.7 | 1 |
| Zach Glotzbecker | Capital | 20:08.8 | 1 |
| Charles Estadt | Marietta | 20:14.5 | 1 |

**Predicted team strength (men, top-5 projected avg):**
| team | team_proj_time |
| --- | --- |
| John Carroll | 24:52.0 |
| Case Western Reserve | 25:02.7 |
| Otterbein | 25:06.0 |
| Wabash | 25:07.8 |
| Allegheny | 25:15.5 |
| Ohio Northern | 25:17.7 |
| Wilmington | 25:18.0 |
| Mount Union | 25:19.8 |

**Rolling-smoothed team projection (men, 3-yr form of top-5):** dampens one-off seasons, aligned with the college cycle.
| team | team_roll_time |
| --- | --- |
| John Carroll | 24:20.1 |
| Otterbein | 24:39.9 |
| Mount Union | 24:40.4 |
| Case Western Reserve | 24:42.0 |
| Allegheny | 24:51.0 |
| Wabash | 24:57.6 |
| Wilmington | 24:58.4 |
| Ohio Northern | 25:00.5 |

## 9. Recruiting reach & athlete origin
From roster hometowns (Sidearm sites). % out-of-state = how national a program's recruiting is. Coverage is partial (origin known for a subset of athletes).


**Men — most national rosters:**
| team | athletes_with_origin | pct_out_of_state | n_states |
| --- | --- | --- | --- |
| Oberlin | 62 | 93.5 | 24 |
| Kenyon | 57 | 86.0 | 24 |
| Denison | 57 | 77.2 | 15 |
| Case Western Reserve | 93 | 69.9 | 24 |
| Wooster | 53 | 66.0 | 18 |
| Baldwin Wallace | 60 | 23.3 | 7 |

**Women — most national rosters:**
| team | athletes_with_origin | pct_out_of_state | n_states |
| --- | --- | --- | --- |
| Oberlin | 78 | 91.0 | 24 |
| Kenyon | 74 | 83.8 | 25 |
| Case Western Reserve | 72 | 77.8 | 21 |
| Denison | 45 | 71.1 | 20 |
| Wooster | 69 | 59.4 | 19 |
| Hiram | 20 | 30.0 | 5 |

**Development by origin** (in-state vs out-of-state; debut & improvement in std-distance seconds):
| gender | origin | athletes | mean_debut_s | mean_improve_s |
| --- | --- | --- | --- | --- |
| men | in-state (OH) | 305 | 1686.1 | 69.1 |
| men | out-of-state | 186 | 1675.3 | 55.6 |
| women | in-state (OH) | 274 | 1542.1 | 54.3 |
| women | out-of-state | 198 | 1512.7 | 56.1 |

## 10. Dynamics & coaching impact
_Descriptive & correlational — confounded by graduation cohorts, small rosters, the 2020 gap, and 2024 changes being too recent to read._


**Men — improvement rate by trailing window** (s/yr in top-5 time; negative = getting faster) + 2yr‑vs‑10yr acceleration:
| team | rate_10yr | rate_5yr | rate_2yr | accel_2v10 |
| --- | --- | --- | --- | --- |
| Defiance | 21.2 | -168.8 | -322.8 | -344.0 |
| Capital | -12.2 | -62.5 | -29.6 | -17.4 |
| Marietta | -30.5 | -29.5 | -17.7 | 12.8 |
| Baldwin Wallace | -4.6 | -21.1 | -5.5 | -0.9 |
| Kenyon | -8.5 | -20.3 | -42.3 | -33.8 |
| Oberlin | -6.7 | -10.0 | 11.4 | 18.1 |
| Wabash | 3.5 | -5.2 | 15.8 | 12.3 |
| Ohio Northern | 0.1 | -4.8 | 27.7 | 27.6 |

**Women — improvement rate by trailing window** (s/yr in top-5 time; negative = getting faster) + 2yr‑vs‑10yr acceleration:
| team | rate_10yr | rate_5yr | rate_2yr | accel_2v10 |
| --- | --- | --- | --- | --- |
| Marietta | -24.9 | -83.8 | -309.3 | -284.4 |
| Capital | -22.0 | -81.2 | -349.0 | -326.9 |
| Muskingum | 2.4 | -71.9 | 34.2 | 31.8 |
| Ohio Wesleyan | -3.2 | -42.0 | -8.1 | -4.9 |
| Hiram | -32.4 | -32.4 | -5.3 | 27.1 |
| Otterbein | 7.6 | -21.5 | 10.7 | 3.0 |
| Denison | -1.3 | -10.1 | -21.9 | -20.5 |
| Wilmington | -13.4 | -8.2 | 27.1 | 40.5 |

> Read the **5‑yr** rate as the stable trend; 1–2‑yr swings are dominated by graduating classes (small programs move wildly).

### Coaching-change effect — within-athlete DiD + placebo pre-trend test (airtight)
**Treated** = returners racing before *and* after the change; **control** = returners at programs with no change over the same years. **DiD<0** = the coach's returners improved more than comparable runners elsewhere. The **placebo** re-runs the DiD on a fake change `k` years earlier (both windows pre-treatment): a null placebo supports parallel trends (**CREDIBLE**); a significant placebo means a pre-existing trend (**SUSPECT**). 90% bootstrap CI.

| team | gender | change_year | new_coach | n_treated | did_s | ci_lo | ci_hi | placebo_did_s | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Kenyon | women | 2020 | Ciara Kissane | 7 | -106.3 | -178.2 | -39.5 | -16.7 | CREDIBLE (passes placebo) |
| Kenyon | men | 2020 | Ciara Kissane | 9 | -35.4 | -100.1 | 31.9 | 4.9 | null |
| Kenyon | men | 2023 | Kirk Shellhouse | 12 | -33.3 | -65.5 | -3.2 | nan | significant (pre-trend untested) |
| Kenyon | women | 2023 | Kirk Shellhouse | 5 | -20.8 | -61.9 | 18.9 | nan | null |
| John Carroll | women | 2024 | Steve Fuelling | 17 | -13.7 | -51.6 | 23.9 | -48.0 | null |
| Wittenberg | men | 2019 | Paris Hilliard | 6 | -12.6 | -44.2 | 19.6 | nan | null |
| Heidelberg | men | 2024 | Daniel Simpson | 8 | -10.7 | -61.9 | 39.9 | 31.5 | null |
| Oberlin | men | 2024 | Izzy Alexander | 10 | 0.3 | -47.7 | 45.9 | 9.1 | null |
| Wittenberg | women | 2019 | Paris Hilliard | 9 | 2.7 | -40.5 | 45.1 | nan | null |
| Ohio Wesleyan | men | 2023 | Ben Carlson | 12 | 7.0 | -34.5 | 51.2 | -45.2 | null |
| John Carroll | men | 2024 | Steve Fuelling | 20 | 8.1 | -16.5 | 33.4 | -59.7 | null |
| Oberlin | women | 2024 | Izzy Alexander | 9 | 14.8 | -95.6 | 153.6 | -20.2 | null |
| Heidelberg | women | 2024 | Daniel Simpson | 8 | 29.4 | -31.5 | 94.3 | nan | null |
| Ohio Wesleyan | women | 2023 | Ben Carlson | 7 | 30.8 | -4.5 | 66.0 | -84.0 | null |

> **After the placebo gate, exactly one change is fully credible: Kenyon women 2020 (Kissane), DiD −113s, placebo −18 (n.s.).** Kenyon men 2023 (Shellhouse, −32s) is significant but the placebo is untestable (insufficient pre-2020 history). Crucially the placebo **disqualifies** several naive stories: John Carroll (Fuelling) shows a *significant placebo* (−62s) — the program was already on a strong pre-trend that then flattened, so its ~0 real DiD must not be read as a coaching effect; same for Ohio Wesleyan 2023. This is the guardrail that will matter at national scale.

_Assumptions: parallel trends (now tested via placebo) and comparable career-stage mix; control is pooled stable-coach programs. Raw before/after + recruiting shifts remain in the dashboard for context, not causal use._

## 11. National context — NCAA DIII Championships
The full 32‑team national field is ingested as **context only** (national teams tagged `tracked=False`; they never enter the Ohio ratings/development/coaching analyses). 2020 cancelled.


**Men — Ohio at nationals vs the field:**
| season | ohio_qualifiers | best_ohio_team | best_ohio_place | national_champion |
| --- | --- | --- | --- | --- |
| 2016 | 3 | Ohio Northern | 14 | North Central (Ill.) |
| 2017 | 2 | DePauw | 18 | North Central (Ill.) |
| 2018 | 3 | DePauw | 20 | North Central (Ill.) |
| 2019 | 3 | John Carroll | 19 | Pomona-Pitzer |
| 2021 | 3 | John Carroll | 4 | Pomona-Pitzer |
| 2022 | 4 | John Carroll | 4 | MIT |
| 2023 | 2 | John Carroll | 20 | Pomona-Pitzer |
| 2024 | 1 | John Carroll | 30 | Wis.-La Crosse |
| 2025 | 0 | None | <NA> | Wis.-La Crosse |

**Women — Ohio at nationals vs the field:**
| season | ohio_qualifiers | best_ohio_team | best_ohio_place | national_champion |
| --- | --- | --- | --- | --- |
| 2016 | 1 | Allegheny | 13 | Johns Hopkins |
| 2017 | 2 | Allegheny | 18 | Johns Hopkins |
| 2018 | 4 | Allegheny | 13 | Washington U. |
| 2019 | 4 | Oberlin | 11 | Johns Hopkins |
| 2021 | 3 | John Carroll | 23 | Johns Hopkins |
| 2022 | 2 | John Carroll | 19 | Johns Hopkins |
| 2023 | 1 | DePauw | 20 | Carleton |
| 2024 | 1 | DePauw | 29 | MIT |
| 2025 | 0 | None | <NA> | NYU |

**Ohio All-Americans (top‑40 individuals at nationals) by program:**
| team | gender | all_americans |
| --- | --- | --- |
| John Carroll | men | 6 |
| Wilmington | men | 3 |
| Allegheny | women | 3 |
| Otterbein | women | 3 |
| Ohio Northern | men | 3 |
| Allegheny | men | 2 |
| Otterbein | men | 2 |
| Case Western Reserve | women | 2 |
| Case Western Reserve | men | 2 |
| Wabash | men | 2 |
| Kenyon | women | 1 |
| DePauw | men | 1 |

> Best Ohio showings of the decade: **John Carroll men 4th (2021 & 2022)**; national titles went to North Central (Ill.), Pomona‑Pitzer, MIT, and Wis.‑La Crosse. John Carroll leads Ohio with 6 men's All‑Americans.

## 12. Standardized tiers — course- & distance-neutral VDOT (relative index)
XC times are confounded by course/terrain/conditions and varying length. We convert every performance to **VDOT** (fixes distance) and course-adjust via a meet-difficulty model. **Use adjVDOT as a RELATIVE index**: the meet coefficients absorb more than pure course, so the absolute VDOT→5k equivalents below are *indicative only, not calibrated PRs*. Reliable within the connected conference circuit; the national meet is under-identified on this scale (use finish place there).


**Men — team top-5 to win (relative adjVDOT; higher = fitter):**
| tier | median_vdot | equiv_5k_indicative | years |
| --- | --- | --- | --- |
| Win NCAC | 65.2 | 15:51.8 | 9 |
| Win OAC | 67.4 | 15:25.5 | 9 |

**Women — team top-5 to win (relative adjVDOT; higher = fitter):**
| tier | median_vdot | equiv_5k_indicative | years |
| --- | --- | --- | --- |
| Win NCAC | 63.5 | 16:13.4 | 9 |
| Win OAC | 66.7 | 15:34.0 | 9 |

> The clean, trustworthy read is **relative**: the **OAC is a tougher conference to win than the NCAC** on a course/distance-neutral basis (both genders), and rolling 5/3/1-yr the winning bar is **stable to slightly softer** — so the raw-time 'jump' was course/distance artifact, not a real rise in the bar to win. Absolute VDOT/5k values are approximate pending further calibration.

---
### Methodology
- **PacePower**: recency-weighted (EWMA span 3) pace per athlete; predicts next-race pace, projected to 8k (men)/6k (women).
- **Elo**: chronological head-to-head, updated per race; team strength = top-5 mean. Used for team-placement forecasting.
- **Validation**: temporal holdout; pairwise finish-order concordance and Spearman rank correlation, all out-of-sample.
