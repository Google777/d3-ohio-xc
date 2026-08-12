"""Interactive dashboard for D3 Ohio XC program development.

Run with:
    streamlit run src/d3xc/dashboard/app.py
(the pipeline must have data first: python scripts/seed_sample.py  OR a real scrape)
"""
from __future__ import annotations

import sys
from pathlib import Path

# make the src-layout package importable when run via `streamlit run`
SRC = Path(__file__).resolve().parents[2]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from d3xc import config
from d3xc.analyze import metrics as m
from d3xc.scrape.timeutil import seconds_to_time
from d3xc.lactic import programs as lprograms
from d3xc.lactic import ratings as lratings
from d3xc.lactic import projection as lprojection
from d3xc.lactic import elo as lelo
from d3xc.lactic import power as lpower
from d3xc.lactic import validate as lvalidate
from d3xc.analyze import stats as lstats
from d3xc.analyze import coaching as lcoaching
from d3xc.analyze import national as lnational
from d3xc.analyze import standardize as lstandardize
from d3xc.analyze import project as lproject

st.set_page_config(page_title="D3 Ohio XC · LacTiC", layout="wide")

COACH_COLORS = px.colors.qualitative.Pastel


@st.cache_data(show_spinner=False)
def get_frames():
    if not config.DB_PATH.exists():
        return None
    return m.load_frames()


@st.cache_data(show_spinner="Computing LacTiC runner ratings…")
def get_ratings():
    return lratings.load_and_rate()


@st.cache_data(show_spinner="Ranking programs & building tiers…")
def get_programs():
    return lprograms.load_and_rank()  # (strength, tiers)


@st.cache_data(show_spinner="Training LacTiC development model…")
def get_projection():
    return lprojection.run_projection()


@st.cache_data(show_spinner="Computing Elo ratings…")
def get_elo():
    return lelo.load_and_run()


@st.cache_data(show_spinner="Computing PacePower ratings…")
def get_pace_power():
    return lpower.load_and_run()


@st.cache_data(show_spinner="Validating predictions…")
def get_validation():
    frames = get_frames()
    h = get_elo()
    acc = lvalidate.pairwise_accuracy(h, frames["results"], {2024, 2025})
    team = lvalidate.team_placement_prediction(h, frames["placements"], {2024, 2025})
    return acc, team


@st.cache_data(show_spinner="Analyzing coaching dynamics…")
def get_coaching():
    frames = get_frames()
    return (lcoaching.multiwindow_acceleration(frames),
            lcoaching.coaching_change_effect(frames, k=3),
            lcoaching.coaching_change_did(frames, k=3, min_group=5))


@st.cache_data(show_spinner="Standardizing to course/distance-neutral VDOT…")
def get_standardized():
    frames = get_frames()
    adf = lstandardize.course_adjusted_performances(frames["results"])
    return (lstandardize.vdot_tier_summary(frames),
            lstandardize.team_standardized_strength(frames, adf))


@st.cache_resource(show_spinner="Building projection model…")
def get_team_projection():
    return lproject.project_teams(get_frames(), to_year=2029)


@st.cache_resource(show_spinner="Preparing scenario engine…")
def get_prep():
    return lproject._prep(get_frames())


def fmt_time_axis(fig, seconds_col_name="value"):
    """Convert a seconds y-axis to MM:SS tick labels."""
    fig.update_yaxes(
        tickformat=None,
        title="time (MM:SS, projected to std distance)",
    )
    return fig


def add_coaching_overlays(fig: go.Figure, coaches_df: pd.DataFrame):
    """Shade coaching eras behind a season-based figure."""
    if coaches_df is None or coaches_df.empty:
        return
    for i, row in coaches_df.iterrows():
        fig.add_vrect(
            x0=row["start_year"] - 0.5,
            x1=row["end_year"] + 0.5,
            fillcolor=COACH_COLORS[i % len(COACH_COLORS)],
            opacity=0.18,
            line_width=0,
            annotation_text=row["coach_name"],
            annotation_position="top left",
            annotation_font_size=10,
        )


def _gate():
    """Optional password gate. Active ONLY if 'app_password' is set in Streamlit
    secrets (i.e. on the hosted deployment). Local runs and the offline zip stay
    open, so nothing changes for those."""
    try:
        expected = st.secrets["app_password"]
    except Exception:
        return                      # no secrets configured -> open
    if not expected or st.session_state.get("auth_ok"):
        return
    st.title("🏃 D3 Ohio XC — Coach Dashboard")
    st.caption("Private beta — please enter the access password.")
    pw = st.text_input("Access password", type="password")
    if pw:
        import hmac
        if hmac.compare_digest(str(pw), str(expected)):
            st.session_state["auth_ok"] = True
            st.rerun()
        st.error("Incorrect password — try again.")
    st.stop()


def main():
    _gate()
    st.title("🏃 NCAA D3 Ohio Cross Country — Program Development")
    st.caption(
        f"{config.FIRST_SEASON}–{config.LAST_SEASON} · Region VI (Great Lakes) · "
        "source: TFRRS (college), curated coaching data, best-effort HS linkage"
    )

    frames = get_frames()
    if frames is None:
        st.error(
            "No database found. Build data first:\n\n"
            "`python scripts/seed_sample.py`  (synthetic demo)\n\n"
            "or run a real scrape via `python scripts/run_scrape.py`."
        )
        st.stop()

    results = frames["results"]
    placements = frames["placements"]
    coaches = frames["coaches"]
    hs = frames["hs"]

    genders = sorted(results["gender"].dropna().unique().tolist())
    conferences = sorted(results["conference"].dropna().unique().tolist())

    views = ["Coach Mode", "📖 How it works", "LacTiC (predictive)", "Statistics",
             "Coaching & Dynamics", "National", "Standardized (VDOT)", "Scenario",
             "LacTiC Rankings", "Team development", "Most improved", "Conference",
             "Regional & National", "HS → College"]
    qp = st.query_params
    default_view = qp.get("view", views[0])
    view_idx = views.index(default_view) if default_view in views else 0
    default_gender = qp.get("gender", genders[0] if genders else None)
    gender_idx = genders.index(default_gender) if default_gender in genders else 0

    with st.sidebar:
        st.header("Filters")
        gender = st.radio("Gender", genders, index=gender_idx)
        view = st.radio("View", views, index=view_idx)
        conf_filter = st.multiselect("Conferences", conferences, default=conferences)
        window = st.selectbox(
            "Time window",
            [f"All ({config.FIRST_SEASON}–{config.LAST_SEASON})",
             "Last 5 years", "Last 3 years", "Last 1 year"],
            help="Applies to the per-season tables (Conference, Regional & National, "
                 "Team development, Most improved, HS → College). The model views "
                 "(LacTiC, Statistics, Coaching, Standardized, National) always use "
                 "the full history — they need it for ratings and calibration.")

    win_years = {"Last 1 year": 1, "Last 3 years": 3, "Last 5 years": 5}.get(window)
    min_season = config.LAST_SEASON - win_years + 1 if win_years else config.FIRST_SEASON

    r_g = results[(results["gender"] == gender) & (results["conference"].isin(conf_filter))
                  & (results["season"] >= min_season)]
    p_g = placements[(placements["gender"] == gender) & (placements["conference"].isin(conf_filter))
                     & (placements["season"] >= min_season)]
    if win_years:
        st.caption(f"⏱️ Showing the last {win_years} year(s): "
                   f"{min_season}–{config.LAST_SEASON}.")

    if view == "Coach Mode":
        render_coach(gender)
    elif view == "📖 How it works":
        render_readme()
    elif view == "Team development":
        render_team_development(r_g, p_g, coaches, gender)
    elif view == "Most improved":
        render_most_improved(r_g, p_g)
    elif view == "Conference":
        render_conference(p_g)
    elif view == "Regional & National":
        render_regional_national(p_g)
    elif view == "HS → College":
        render_hs_to_college(r_g, hs)
    elif view == "LacTiC Rankings":
        render_lactic(gender, conf_filter)
    elif view == "LacTiC (predictive)":
        render_lactic_predictive(gender, conf_filter)
    elif view == "Statistics":
        render_statistics(gender)
    elif view == "Coaching & Dynamics":
        render_coaching(gender)
    elif view == "National":
        render_national(gender)
    elif view == "Standardized (VDOT)":
        render_standardized(gender)
    elif view == "Scenario":
        render_scenario(gender)


# --------------------------------------------------------------------------
def render_team_development(results, placements, coaches, gender):
    if "tracked" in results.columns:
        results = results[results["tracked"]]
    teams = sorted(results["team"].dropna().unique().tolist())
    if not teams:
        st.info("No data for this selection.")
        return
    prev = st.session_state.get("td_team_sel")
    idx = teams.index(prev) if prev in teams else 0
    team = st.selectbox("Team", teams, index=idx)
    st.session_state["td_team_sel"] = team
    roll_w = st.slider(
        "Rolling window (seasons)", 1, 3, 3,
        help="Smooths year-to-year swings; a 3-season window aligns with the "
             "college cycle. 1 = raw single-season values.")
    scoring = m.team_scoring_by_season(results)
    ts = scoring[scoring["team"] == team].sort_values("season")
    ts = ts.copy()
    ts["top5_roll"] = ts["top5_avg"].rolling(roll_w, min_periods=1).mean()

    c1, c2 = st.columns(2)
    with c1:
        st.subheader(f"Scoring average — raw vs {roll_w}-yr rolling")
        base = ts.dropna(subset=["top5_avg"])
        if base.empty:
            st.info("Not enough athletes per season to compute scoring average.")
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=base["season"], y=base["top5_avg"], mode="markers+lines",
                name="top-5 (raw)", line=dict(color="#c7cdd6"),
                hovertext=base["top5_avg"].map(seconds_to_time)))
            fig.add_trace(go.Scatter(
                x=base["season"], y=base["top5_roll"], mode="lines",
                name=f"top-5 ({roll_w}-yr avg)", line=dict(color="#2c7fb8", width=3),
                hovertext=base["top5_roll"].map(seconds_to_time)))
            fig.update_yaxes(autorange="reversed", title="scoring avg (sec, faster=up)")
            add_coaching_overlays(fig, m.coaching_overlays(coaches, team, gender))
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("1–5 pack spread")
        sp = ts.dropna(subset=["spread_1_5"])
        if sp.empty:
            st.info("Not enough athletes to compute pack spread.")
        else:
            fig = px.bar(sp, x="season", y="spread_1_5")
            fig.update_yaxes(title="1st→5th gap (seconds, smaller=tighter)")
            add_coaching_overlays(fig, m.coaching_overlays(coaches, team, gender))
            st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"Championship placement — raw vs {roll_w}-yr rolling")
    fig = go.Figure()
    palette = {"conference": "#1b9e77", "regional": "#7570b3", "national": "#d95f02"}
    for kind, label in [("conference", "Conference"), ("regional", "Great Lakes Regional"),
                        ("national", "NCAA Championships")]:
        tr = m.placement_trend(placements, kind)
        tr = tr[tr["team"] == team].sort_values("season")
        if tr.empty:
            continue
        tr = tr.copy()
        tr["roll"] = tr["team_place"].rolling(roll_w, min_periods=1).mean()
        fig.add_trace(go.Scatter(x=tr["season"], y=tr["team_place"], mode="markers",
                                 name=f"{label} (raw)", marker=dict(color=palette[kind], size=6, opacity=0.4)))
        fig.add_trace(go.Scatter(x=tr["season"], y=tr["roll"], mode="lines",
                                 name=f"{label} ({roll_w}-yr)", line=dict(color=palette[kind], width=3)))
    fig.update_yaxes(autorange="reversed", title="place (1 = best)")
    add_coaching_overlays(fig, m.coaching_overlays(coaches, team, gender))
    if fig.data:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No placement data for this team.")


def render_most_improved(results, placements):
    st.subheader("Most improved athletes (debut season → career best)")
    mi = m.most_improved_athletes(results)
    if mi.empty:
        st.info("Need athletes with ≥2 seasons of data.")
    else:
        top = mi.head(25).copy()
        top["debut"] = top["debut_time"].map(seconds_to_time)
        top["best"] = top["best_time"].map(seconds_to_time)
        top["Δ"] = top["improvement_seconds"].round(1)
        fig = px.bar(top.iloc[::-1], x="improvement_seconds", y="athlete_name",
                     color="team", orientation="h",
                     hover_data=["debut", "best", "improvement_pct"])
        fig.update_xaxes(title="improvement (seconds faster)")
        fig.update_layout(height=650)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            top[["athlete_name", "team", "conference", "debut_season", "seasons",
                 "debut", "best", "Δ", "improvement_pct"]],
            use_container_width=True, hide_index=True,
        )

    st.subheader("Most improved teams (regional placement gained)")
    mt = m.most_improved_teams(placements, "regional")
    if mt.empty:
        st.info("Need teams with ≥2 seasons of regional placements.")
    else:
        st.dataframe(mt, use_container_width=True, hide_index=True)


def render_conference(placements):
    st.subheader("Conference titles")
    cw = m.conference_wins(placements)
    if cw.empty:
        st.info("No conference wins in the selection.")
    else:
        fig = px.bar(cw.head(20), x="conference_titles", y="team", orientation="h",
                     color="conference_titles", color_continuous_scale="Blues")
        fig.update_layout(height=550)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Conference placement trend")
    tr = m.placement_trend(placements, "conference")
    if tr.empty:
        st.info("No conference placement data.")
    else:
        fig = px.line(tr, x="season", y="team_place", color="team", markers=True)
        fig.update_yaxes(autorange="reversed", title="place (1 = best)")
        st.plotly_chart(fig, use_container_width=True)


def render_regional_national(placements):
    st.subheader("Great Lakes Regional placement")
    tr = m.placement_trend(placements, "regional")
    if tr.empty:
        st.info("No regional placement data.")
    else:
        fig = px.line(tr, x="season", y="team_place", color="team", markers=True)
        fig.update_yaxes(autorange="reversed", title="regional place (1 = best)")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("NCAA Championships qualifiers & finish")
    nat = m.placement_trend(placements, "national")
    if nat.empty:
        st.info("No national-meet appearances in the selection.")
    else:
        fig = px.scatter(nat, x="season", y="team_place", color="team", size="team_points",
                         hover_data=["conference"])
        fig.update_yaxes(autorange="reversed", title="national place (1 = best)")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            nat.groupby("team").size().reset_index(name="national_appearances")
            .sort_values("national_appearances", ascending=False),
            use_container_width=True, hide_index=True,
        )


def render_hs_to_college(results, hs):
    st.subheader("High school → college development")
    st.caption(
        "Best-effort linkage of college athletes to their HS marks. "
        "Confidence-gated; fuzzy name matching means some links are approximate."
    )
    conf = st.slider("Minimum link confidence", 0.0, 1.0, 0.6, 0.05)
    h2c = m.hs_to_college(results, hs, min_confidence=conf)
    if h2c.empty:
        st.info("No linked HS marks at this confidence threshold.")
        return
    fig = px.histogram(h2c, x="pace_improvement_pct", nbins=30, color="gender")
    fig.update_xaxes(title="pace improvement HS→college (%)")
    st.plotly_chart(fig, use_container_width=True)

    show = h2c[["athlete_name", "team", "gender", "event", "hs_pace",
                "college_best_pace", "pace_improvement_pct", "match_confidence"]].copy()
    show["hs_pace"] = show["hs_pace"].round(1)
    show["college_best_pace"] = show["college_best_pace"].round(1)
    show["pace_improvement_pct"] = show["pace_improvement_pct"].round(2)
    st.dataframe(show.head(50), use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------
# LacTiC ML rankings
# --------------------------------------------------------------------------
def render_lactic(gender, conf_filter):
    st.subheader("LacTiC — ML rankings for runners & programs")
    st.caption(
        "Runner ratings are meet-adjusted (ridge model removes course/field "
        "difficulty); program tiers cluster current strength × trajectory; the "
        "development model is gradient-boosted and flags athletes who beat their "
        "projected pace."
    )
    ar = get_ratings()
    strength, tiers = get_programs()
    proj = get_projection()

    ar = ar[(ar["gender"] == gender) & (ar["conference"].isin(conf_filter))]
    strength_g = strength[(strength["gender"] == gender)
                          & (strength["conference"].isin(conf_filter))]
    tiers_g = tiers[(tiers["gender"] == gender)
                    & (tiers["conference"].isin(conf_filter))]

    t_run, t_prog, t_dev, t_proj = st.tabs(
        ["🏅 Runners", "🏫 Programs & tiers", "📈 Most improved vs expected",
         "🔮 Projections"]
    )

    with t_run:
        seasons = sorted(ar["season"].dropna().unique().tolist())
        if not seasons:
            st.info("No ratings for this selection.")
        else:
            season = st.selectbox("Season", seasons, index=len(seasons) - 1,
                                  key="lactic_run_season")
            top = lratings.top_runners(ar, gender, season, 30)
            fig = px.bar(top.iloc[::-1], x="rating", y="athlete_name",
                         color="team", orientation="h",
                         hover_data=["adj_pace_sec_per_km", "races", "rank_in_group"])
            fig.update_layout(height=700)
            fig.update_xaxes(title="LacTiC rating (higher = faster, meet-adjusted)")
            st.plotly_chart(fig, use_container_width=True)
            show = top[["rank_in_group", "athlete_name", "team", "conference",
                        "adj_pace_sec_per_km", "rating", "races"]].copy()
            show["adj_pace_sec_per_km"] = show["adj_pace_sec_per_km"].round(1)
            show["rating"] = show["rating"].round(1)
            st.dataframe(show, use_container_width=True, hide_index=True)

    with t_prog:
        if strength_g.empty:
            st.info("No program strength for this selection.")
        else:
            seasons = sorted(strength_g["season"].unique().tolist())
            season = st.selectbox("Season", seasons, index=len(seasons) - 1,
                                  key="lactic_prog_season")
            rank = lprograms.rank_programs(strength_g, gender, season)
            st.markdown(f"**Program ranking — {season}**")
            st.dataframe(
                rank[["rank", "team", "conference", "program_adj_pace",
                      "program_rating", "n_scorers"]].round(1),
                use_container_width=True, hide_index=True,
            )
            st.markdown("**Tiers — current strength × development trajectory**")
            if not tiers_g.empty:
                fig = px.scatter(
                    tiers_g, x="improvement_rate", y="latest_rating",
                    color="tier_label", text="team", symbol="trend",
                    hover_data=["conference", "seasons_tracked"],
                )
                fig.update_traces(textposition="top center")
                fig.update_xaxes(title="improvement rate (→ faster over time)")
                fig.update_yaxes(title="latest program rating")
                fig.update_layout(height=550)
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(
                    tiers_g[["team", "conference", "tier", "tier_label", "trend",
                             "latest_rating", "improvement_rate"]].round(3)
                    .sort_values(["tier", "latest_rating"], ascending=[True, False]),
                    use_container_width=True, hide_index=True,
                )

    with t_dev:
        st.caption(
            "Residual = actual − model-predicted next-season pace (out-of-fold). "
            "Negative = ran faster than expected given profile."
        )
        if proj.over_under.empty:
            st.info("Not enough season-to-season transitions to model.")
        else:
            ou = proj.over_under[proj.over_under["gender"] == gender]
            over = ou.head(25).copy()
            over["overperformance"] = (-over["residual"]).round(2)
            fig = px.bar(over.iloc[::-1], x="overperformance", y="athlete_name",
                         color="team", orientation="h",
                         hover_data=["from_season", "to_season",
                                     "actual_improvement", "expected_improvement"])
            fig.update_xaxes(title="beat projection by (sec/km)")
            fig.update_layout(height=650)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(
                over[["athlete_name", "team", "from_season", "to_season",
                      "prev_adj_pace", "actual_pace", "predicted_pace",
                      "overperformance"]].round(2),
                use_container_width=True, hide_index=True,
            )
        c1, c2, c3 = st.columns(3)
        c1.metric("Model CV MAE (sec/km)", f"{proj.cv_mae:.3f}")
        c2.metric("Persistence baseline", f"{proj.baseline_mae:.3f}")
        c3.metric("Skill vs baseline", f"{proj.skill_vs_baseline*100:.0f}%")
        if proj.importances:
            imp = pd.DataFrame(
                {"feature": list(proj.importances), "importance": list(proj.importances.values())}
            )
            st.plotly_chart(px.bar(imp, x="importance", y="feature", orientation="h"),
                            use_container_width=True)

    with t_proj:
        st.caption("Predicted next-season pace for athletes active in the final season.")
        if proj.projections.empty:
            st.info("No returning athletes to project.")
        else:
            pj = proj.projections[proj.projections["gender"] == gender].head(30)
            fig = px.bar(pj.iloc[::-1], x="projected_improvement", y="athlete_name",
                         color="team", orientation="h",
                         hover_data=["prev_adj_pace", "projected_pace", "seasons_run"])
            fig.update_xaxes(title="projected improvement next season (sec/km)")
            fig.update_layout(height=650)
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(
                pj[["athlete_name", "team", "prev_adj_pace", "projected_pace",
                    "projected_improvement", "seasons_run"]].round(2),
                use_container_width=True, hide_index=True,
            )


def render_lactic_predictive(gender, conf_filter):
    st.subheader("LacTiC (predictive) — validated out-of-sample")
    st.caption(
        "PacePower = recency-weighted pace (best individual predictor, ~87% "
        "pairwise accuracy). Elo = head-to-head (best for team outcomes). All "
        "metrics below are from a temporal holdout — no peeking at the future."
    )
    frames = get_frames()
    team_conf = frames["teams"].set_index("name")["conference"].to_dict()
    pp = get_pace_power()
    pp = pp[pp["gender"] == gender].copy()
    pp["conference"] = pp["team"].map(team_conf)
    pp = pp[pp["conference"].isin(conf_filter)]
    elo_hist = get_elo()
    acc, team = get_validation()

    t_pred, t_team, t_elo, t_val = st.tabs(
        ["🔮 Predicted runners", "🏫 Predicted teams", "⚔️ Elo (head-to-head)",
         "✅ Predictive validation"])

    with t_pred:
        top = pp.head(30)
        fig = px.bar(top.iloc[::-1], x="rating", y="athlete_name", color="team",
                     orientation="h", hover_data=["proj_time", "races"])
        fig.update_layout(height=700)
        fig.update_xaxes(title="PacePower rating (higher = faster, predicted)")
        st.plotly_chart(fig, use_container_width=True)
        show = top[["athlete_name", "team", "proj_time", "rating", "races"]].copy()
        show["rating"] = show["rating"].round(1)
        st.dataframe(show, use_container_width=True, hide_index=True)

    with t_team:
        rw = st.slider("Rolling window for smoothed projection (seasons)", 1, 3, 3,
                       key="proj_roll")
        tp = lpower.team_pace_power(frames["results"])
        tp = tp[tp["gender"] == gender].copy()
        tp["conference"] = tp["team"].map(team_conf)
        tp = tp[tp["conference"].isin(conf_filter)].reset_index(drop=True)
        tp.insert(0, "rank", tp.index + 1)
        rt = lpower.rolling_team_projection(frames["results"], window=rw)
        rt = rt[rt["gender"] == gender].copy()
        rt["conference"] = rt["team"].map(team_conf)
        rt = rt[rt["conference"].isin(conf_filter)].reset_index(drop=True)
        rt.insert(0, "rank", rt.index + 1)
        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown("**Latest-form projection** (EWMA of top 5):")
            st.dataframe(tp[["rank", "team", "conference", "team_proj_time"]],
                         use_container_width=True, hide_index=True)
        with cc2:
            st.markdown(f"**{rw}-yr smoothed projection** (rolling top 5):")
            st.dataframe(rt[["rank", "team", "conference", "team_roll_time"]],
                         use_container_width=True, hide_index=True)

    with t_elo:
        cur = lelo.current_ratings(elo_hist)
        cur = cur[cur["gender"] == gender].copy()
        cur["conference"] = cur["team"].map(team_conf)
        cur = cur[cur["conference"].isin(conf_filter)].head(25)
        fig = px.bar(cur.iloc[::-1], x="elo", y="athlete_name", color="team",
                     orientation="h", hover_data=["season"])
        fig.update_layout(height=650)
        fig.update_xaxes(title="Elo (head-to-head)")
        st.plotly_chart(fig, use_container_width=True)

    with t_val:
        st.markdown("**Individual finish-order accuracy** (2024–25 holdout, "
                    f"{acc['races']} races) — % of runner pairs ordered correctly:")
        table = pd.DataFrame({
            "predictor": ["PacePower (recency pace)", "Blend Elo+best", "Last-race pace",
                          "Career-best pace", "Meet-adj recency", "Head-to-head Elo", "Coin flip"],
            "accuracy": [acc["ewma_pace_accuracy"], acc["blend_accuracy"],
                         acc["last_pace_accuracy"], acc["prev_best_pace_accuracy"],
                         acc["madj_ewma_accuracy"], acc["pre_elo_accuracy"], 0.5],
        })
        fig = px.bar(table.iloc[::-1], x="accuracy", y="predictor", orientation="h")
        fig.update_xaxes(tickformat=".0%", title="pairwise accuracy (out-of-sample)")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
        c1, c2 = st.columns(2)
        c1.metric("Best individual predictor", f"{acc['ewma_pace_accuracy']*100:.1f}%",
                  "PacePower")
        c2.metric("Team-placement prediction", f"ρ = {team['mean_spearman']:.2f}",
                  f"{team['meets_evaluated']} champ meets")


def render_statistics(gender):
    st.subheader("Statistics — development, balance, realignment")
    frames = get_frames()
    traj = lstats.program_trajectories(frames)
    tg = traj[traj["gender"] == gender].dropna(subset=["reg_slope_place_per_yr"])

    st.markdown("**Program development** — regional places gained per year "
                "(negative = rising). Bars shaded by statistical significance.")
    tg = tg.sort_values("reg_slope_place_per_yr")
    tg["significant"] = np.where(tg["reg_p"] < 0.05, "p < 0.05", "n.s.")
    fig = px.bar(tg, x="reg_slope_place_per_yr", y="team", color="significant",
                 orientation="h", hover_data=["reg_r2", "reg_p"],
                 color_discrete_map={"p < 0.05": "#2c7fb8", "n.s.": "#c7cdd6"})
    fig.update_layout(height=600)
    fig.update_xaxes(title="Δ regional place / year (← rising | falling →)")
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Conference titles**")
        tc = lstats.title_counts(frames["placements"])
        st.dataframe(tc[tc.gender == gender].head(10), use_container_width=True, hide_index=True)
    with c2:
        st.markdown("**National appearances**")
        na = lstats.national_appearances(frames["placements"])
        st.dataframe(na[na.gender == gender].head(10), use_container_width=True, hide_index=True)

    st.markdown("**The John Carroll → NCAC realignment (2025)**")
    rip = lstats.jcu_ncac_ripple(frames)
    oac = rip["oac_men_champions"]
    st.write("OAC men champions: " + ", ".join(f"{y}: {t}" for y, t in sorted(oac.items())))
    shift = pd.DataFrame(rip["ncac_men_shift_2025_vs_2021_24"]).dropna(subset=["delta_places"])
    if not shift.empty:
        st.caption("NCAC Ohio men — mean placement 2025 vs 2021–24 (+ = pushed down after JCU joined)")
        st.dataframe(shift.sort_values("delta_places"), use_container_width=True, hide_index=True)

    st.markdown("**Program development effect** — improvement beyond arrival "
                "caliber (regression-controlled; the HS→college pipeline signal)")
    from d3xc.analyze import development as D
    eff = D.program_development_effect(frames["results"])
    eff = eff[eff["gender"] == gender].sort_values("dev_effect_s")
    if not eff.empty:
        fig = px.bar(eff, x="dev_effect_s", y="team", orientation="h",
                     color="dev_effect_s", color_continuous_scale="RdYlGn",
                     hover_data=["athletes", "mean_improve_s"])
        fig.update_xaxes(title="development effect (s beyond arrival caliber)")
        fig.update_layout(height=520)
        st.plotly_chart(fig, use_container_width=True)
    ct = D.class_transition_stats(frames["results"])
    ctg = ct[ct["gender"] == gender]
    if not ctg.empty:
        st.caption("Year-over-year improvement by college year (std distance)")
        st.dataframe(ctg[["transition", "n", "mean_improve_s", "median_improve_s"]].round(1),
                     use_container_width=True, hide_index=True)

    st.markdown("**Program development — 3-yr rolling: steadiness vs swing**")
    st.caption("X = smoothed change in top-5 time (← faster/improving). Y = avg "
               "year-to-year swing (volatility). Bottom-left = steady, real risers; "
               "high Y = too swingy to trust single seasons.")
    rc = lstats.rolling_change(frames, window=3)
    rcg = rc[rc["gender"] == gender].dropna(subset=["roll_time_change_s", "mean_yoy_swing_s"])
    if not rcg.empty:
        fig = px.scatter(rcg, x="roll_time_change_s", y="mean_yoy_swing_s",
                         text="team", color="conference",
                         hover_data=["roll_regional_change"])
        fig.update_traces(textposition="top center")
        fig.update_xaxes(title="3-yr smoothed Δ top-5 time (← improving)")
        fig.update_yaxes(title="avg year-to-year swing (s) — volatility")
        fig.update_layout(height=520)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Recruiting reach** — how national is each roster? "
                "(% of athletes with known origin from out of state)")
    rr = lstats.recruiting_reach(frames)
    rrg = rr[rr["gender"] == gender].sort_values("pct_out_of_state")
    if not rrg.empty:
        fig = px.bar(rrg, x="pct_out_of_state", y="team", orientation="h",
                     color="pct_out_of_state", color_continuous_scale="Viridis",
                     hover_data=["athletes_with_origin", "n_states"])
        fig.update_xaxes(title="% out-of-state (→ more national)")
        fig.update_layout(height=520)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Origin coverage is partial (roster hometowns from Sidearm "
                   "sites); Ohio Wesleyan and PrestoSports schools not yet scraped.")


def render_coaching(gender):
    st.subheader("Coaching & Dynamics")
    st.caption("Descriptive & correlational — confounded by graduation cohorts, "
               "small rosters, the 2020 gap, and 2024 changes being too recent. "
               "Read the 5-yr rate as the stable trend.")
    acc, ce, did = get_coaching()

    st.markdown("**Airtight coaching‑change effect — within‑athlete DiD + placebo "
                "pre‑trend test** (returners vs stable‑coach controls; 90% bootstrap "
                "CI). DiD<0 = ran faster than comparable returners elsewhere. Bars "
                "green only if they pass the placebo (parallel trends hold).")
    dg = did[(did["gender"] == gender) & did["sufficient"]].sort_values("did_s")
    if dg.empty:
        st.info("No sufficiently-powered changes for this gender.")
    else:
        dg = dg.copy()
        dg["label"] = dg["team"] + " '" + (dg["change_year"] % 100).astype(str) + " " + dg["new_coach"]
        color_map = {"CREDIBLE (passes placebo)": "#2ca25f",
                     "SUSPECT (pre-trend violation)": "#de2d26",
                     "significant (pre-trend untested)": "#3182bd",
                     "null": "#c7cdd6", "insufficient": "#c7cdd6"}
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=dg["did_s"], y=dg["label"], orientation="h",
            marker_color=[color_map.get(v, "#c7cdd6") for v in dg["verdict"]],
            error_x=dict(type="data", symmetric=False,
                         array=dg["ci_hi"] - dg["did_s"],
                         arrayminus=dg["did_s"] - dg["ci_lo"])))
        fig.add_vline(x=0, line_dash="dash", line_color="#888")
        fig.update_xaxes(title="DiD (s): ← returners improved more | less →")
        fig.update_layout(height=440,
                          title="green=credible · blue=significant, placebo untested · red=suspect")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(dg[["team", "gender", "change_year", "new_coach", "n_treated",
                         "did_s", "ci_lo", "ci_hi", "placebo_did_s", "verdict"]].round(1),
                     use_container_width=True, hide_index=True)
        st.caption("Placebo = same DiD on a fake change k years earlier (both "
                   "windows pre-treatment). A significant placebo (red) means the "
                   "program was already trending, so the real DiD isn't causal — "
                   "e.g., John Carroll/Fuelling. Only Kenyon women 2020 passes clean.")

    st.markdown("**Improvement acceleration** — 2‑yr vs 10‑yr rate of top‑5 time "
                "(negative = improvement accelerating recently)")
    ag = acc[acc["gender"] == gender].dropna(subset=["accel_2v10"]).sort_values("accel_2v10")
    if not ag.empty:
        fig = px.bar(ag, x="accel_2v10", y="team", orientation="h",
                     color="accel_2v10", color_continuous_scale="RdYlGn_r",
                     hover_data=["rate_10yr", "rate_5yr", "rate_2yr"])
        fig.update_xaxes(title="accel (s/yr): ← accelerating improvement | slowing →")
        fig.update_layout(height=520)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(ag[["team", "rate_10yr", "rate_5yr", "rate_2yr", "accel_2v10"]].round(1),
                     use_container_width=True, hide_index=True)

    st.markdown("**Coaching‑change event study (±3 seasons)** — `d_top5_s`<0 = "
                "faster after; `d_regional`<0 = better; `d_oos_pct`>0 = more national")
    ceg = ce[ce["gender"] == gender].sort_values("change_year")
    if ceg.empty:
        st.info("No coaching changes with data for this gender.")
    else:
        plot = ceg.dropna(subset=["d_top5_s"]).copy()
        if not plot.empty:
            plot["label"] = plot["team"] + " '" + (plot["change_year"] % 100).astype(str) + " " + plot["new_coach"]
            fig = px.bar(plot.sort_values("d_top5_s"), x="d_top5_s", y="label",
                         orientation="h", color="d_top5_s",
                         color_continuous_scale="RdYlGn_r",
                         hover_data=["prev_coach", "d_regional", "d_oos_pct"])
            fig.update_xaxes(title="Δ top‑5 time after change (s): ← faster | slower →")
            fig.update_layout(height=460)
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            ceg[["team", "change_year", "prev_coach", "new_coach", "d_top5_s",
                 "d_regional", "d_arrival_s", "d_oos_pct"]].round(1),
            use_container_width=True, hide_index=True)
        st.caption("2024 changes (e.g., John Carroll → Fuelling) read as "
                   "regressions mainly because star cohorts graduated — not the coach.")


def render_national(gender):
    st.subheader("National context — NCAA DIII Championships")
    st.caption("Full 32-team national field as context (national teams are "
               "tracked=False and never enter the Ohio ratings/development "
               "analyses). 2020 cancelled.")
    frames = get_frames()
    oa = lnational.ohio_at_nationals(frames)
    og = oa[oa["gender"] == gender].copy()
    st.markdown("**Ohio at nationals vs the field** (best qualifying team each year)")
    st.dataframe(og[["season", "field_teams", "ohio_qualifiers", "best_ohio_team",
                     "best_ohio_place", "national_champion"]],
                 use_container_width=True, hide_index=True)

    seasons = sorted(og["season"].unique().tolist())
    if seasons:
        yr = st.selectbox("National standings for season", seasons,
                          index=len(seasons) - 1)
        st_df = lnational.national_team_standings(frames, yr, gender)
        st.markdown(f"**{yr} national team standings** (Ohio programs highlighted)")
        def _hl(row):
            return ["background-color: #e8f7ec" if row["ohio"] else "" for _ in row]
        st.dataframe(st_df.style.apply(_hl, axis=1), use_container_width=True, hide_index=True)

    aac = lnational.ohio_all_american_counts(frames)
    aag = aac[aac["gender"] == gender]
    if not aag.empty:
        st.markdown("**Ohio All-Americans (top-40 at nationals) by program**")
        fig = px.bar(aag, x="all_americans", y="team", orientation="h",
                     color="all_americans", color_continuous_scale="Blues")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)


def render_standardized(gender):
    st.subheader("Standardized — course- & distance-neutral VDOT")
    st.caption("Every performance → VDOT (fixes varying length), then course-"
               "adjusted to a championship-course reference. Reliable within the "
               "conference circuit; national meet excluded (under-identified).")
    tier_sum, strength = get_standardized()

    st.markdown("**Relative course/distance-neutral bar to win (adjVDOT; higher = "
                "fitter).** 5k equivalents are *indicative only* — absolute "
                "calibration is approximate; the trustworthy signal is relative "
                "(OAC vs NCAC, and the trend).")
    ts = tier_sum[tier_sum["gender"] == gender].copy()
    if not ts.empty:
        ts["equiv_5k"] = ts["equiv_5k_s"].map(seconds_to_time)
        st.dataframe(ts[["tier", "median_vdot", "equiv_5k", "years"]].round(1),
                     use_container_width=True, hide_index=True)

    st.markdown("**Team standardized strength over time** (top-5 avg adjVDOT; higher = fitter)")
    s = strength[strength["gender"] == gender]
    if not s.empty:
        teams = sorted(s["team"].unique().tolist())
        sel = st.multiselect("Teams", teams,
                             default=[t for t in ["John Carroll", "Otterbein",
                                                  "Ohio Northern", "Denison", "Kenyon"] if t in teams])
        d = s[s["team"].isin(sel)] if sel else s
        fig = px.line(d, x="season", y="team_vdot", color="team", markers=True)
        fig.update_yaxes(title="team top-5 adjVDOT (higher = fitter)")
        st.plotly_chart(fig, use_container_width=True)


def render_scenario(gender):
    import pandas as pd
    st.subheader('Scenario — "What do I need to do as a coach?"')
    st.caption("Course/distance-neutral adjVDOT (relative index; the qualify bar is "
               "cross-validated). Sliders shift recruiting caliber and development "
               "rate relative to the program's own history. ~1 VDOT ≈ 6.5 s/5k.")
    proj, prep, frames = get_team_projection(), get_prep(), get_frames()
    teams = sorted(proj[proj.gender == gender]["team"].unique().tolist())
    if not teams:
        st.info("No teams for this gender.")
        return
    default = "Kenyon" if gender == "men" and "Kenyon" in teams else teams[0]
    if st.session_state.get("scn_team") not in teams:
        st.session_state.pop("scn_team", None)
    team = st.selectbox("Program", teams, index=teams.index(default), key="scn_team")
    row = proj[(proj.team == team) & (proj.gender == gender)].iloc[0]
    conf, cur_arr, QUALIFY = row["conference"], float(row["arrival_vdot"]), lproject.QUALIFY_VDOT.get(gender, 67.1)

    c1, c2 = st.columns(2)
    dA = c1.slider("🎯 Recruiting — incoming class vs history (VDOT)", -2.0, 8.0, 0.0, 0.5,
                   help="+1 VDOT ≈ 6.5 s/5k faster freshmen")
    dev = c2.slider("📈 Development — extra gain per year (VDOT/yr)", 0.0, 3.0, 0.0, 0.1,
                    help="on top of the program's historical class-year improvement")

    years = list(range(2026, 2030))
    scen = lproject.project_scenario(frames, team, gender, arrival=cur_arr + dA,
                                     dev_boost=dev, prep=prep)
    others = proj[(proj.conference == conf) & (proj.gender == gender) & (proj.team != team)]
    title_bar = {y: float(others[f"proj_{y}"].max()) for y in years} if len(others) else {}

    dfp = pd.DataFrame({"season": years,
                        "Your scenario": [scen[y] for y in years],
                        "Baseline (no change)": [float(row[f"proj_{y}"]) for y in years]})
    if title_bar:
        dfp[f"{conf} title bar"] = [title_bar[y] for y in years]
    dfp["Qualify (~67.1)"] = QUALIFY
    long = dfp.melt("season", var_name="series", value_name="adjVDOT")
    fig = px.line(long, x="season", y="adjVDOT", color="series", markers=True)
    fig.update_yaxes(title="team top-5 adjVDOT (higher = fitter)")
    fig.update_xaxes(dtick=1, tickformat="d")
    st.plotly_chart(fig, use_container_width=True)

    fin = scen[2029]
    b1, b2, b3 = st.columns(3)
    b1.metric("Your top-5 by 2029", f"{fin:.1f}")
    if title_bar:
        b2.metric(f"{conf} title bar 2029", f"{title_bar[2029]:.1f}",
                  f"{fin - title_bar[2029]:+.1f}")
    b3.metric("vs qualify (67.1)", f"{fin - QUALIFY:+.1f}",
              "IN" if fin >= QUALIFY else "short")

    st.markdown(f"### 🧭 What does **{team}** need to do?")
    act = lproject.coach_actions(frames, team, gender, prep=prep, proj=proj, qualify=QUALIFY)

    def fmt(v, kind):
        if v is None:
            return "not reachable on this lever alone"
        if kind == "recruit":
            d = v - cur_arr
            return (f"recruit classes at **{v:.1f}** adjVDOT (**+{d:.1f}** vs now, "
                    f"~{d * 6.5:.0f} s/5k faster freshmen)")
        return f"develop **+{v:.1f}/yr** (~{v * 6.5:.0f} s/5k per runner per year)"

    st.markdown(f"**Win the {conf} title** — beat the strongest rival's projection:")
    for y in (2028, 2029):
        t = act["title"][y]
        st.markdown(f"- **By {y}** (bar ≈ {t['bar']:.1f}): {fmt(t['recruit'], 'recruit')}  \n"
                    f"  — *or* {fmt(t['develop'], 'develop')}")
    st.markdown("**Qualify for nationals** — Great Lakes bar ≈ 67.1, by 2029:")
    st.markdown(f"- {fmt(act['qualify_recruit'], 'recruit')}  \n"
                f"  — *or* {fmt(act['qualify_develop'], 'develop')}")
    if act["qualify_recruit"] is None or act["qualify_develop"] is None:
        st.info("Qualifying usually needs a **combined** push — nudge both sliders "
                "(e.g. recruiting +3 and development +1/yr) to watch it clear 67.1.")


def render_coach(gender):
    import pandas as pd
    SPV = 6.5                                     # sec/5k per VDOT point
    QUAL = lproject.QUALIFY_VDOT.get(gender, 67.1)  # gender-specific qualify bar
    qual_time = "25:27 for 8k" if gender == "men" else "22:40 for 6k"
    st.subheader("🏁 Coach Mode — adjust your plan, see what to do")
    st.caption("Plain language, real race times. Slide your recruiting and training "
               "plans below; the model shows where you're headed and what it takes.")
    st.success("✔ Trust check: this model agreed with your **actual conference "
               "finishes 90% of the time** over 2016–2025 (1,172 of 1,304 team "
               "head-to-head matchups), and the national-qualifying line checks out "
               "two independent ways.")

    with st.expander("❓ New here? How to read this page (30-second guide)", expanded=True):
        st.markdown(
            "This page has four parts, top to bottom:\n\n"
            "1. **Where your program stands today** — your team at the end of the "
            "2025 season (your starting point heading into 2026): a fitness score, "
            "your place in the conference, and your incoming recruiting class.\n"
            "2. **Your two goals** — the fitness level (shown as a real race time) "
            "your top‑5 need to **win your conference** and to **qualify for nationals**.\n"
            "3. **Adjust your plan** — two sliders: how much *faster you recruit* and "
            "how much your runners *improve each year*. Drag them and watch the graph "
            "and goals update.\n"
            "4. **What to do** — plain recommendations to reach each goal.\n\n"
            "**Fitness score = VDOT; higher is fitter.** Want the full walkthrough? "
            "Pick **📖 How it works** in the left sidebar.")

    proj, prep, frames = get_team_projection(), get_prep(), get_frames()
    teams = sorted(proj[proj.gender == gender]["team"].unique().tolist())
    if not teams:
        st.info("No teams for this gender.")
        return
    default = "Kenyon" if gender == "men" and "Kenyon" in teams else teams[0]
    if st.session_state.get("coach_team") not in teams:
        st.session_state.pop("coach_team", None)
    team = st.selectbox("Your program", teams, index=teams.index(default),
                        key="coach_team")
    row = proj[(proj.team == team) & (proj.gender == gender)].iloc[0]
    conf, cur_arr = row["conference"], float(row["arrival_vdot"])

    # ---- where you stand right now (2025) ----
    st.markdown("### 📍 Where your program stands today")
    st.caption("End of the 2025 season — your starting point heading into 2026.")
    cur_conf = (proj[(proj.conference == conf) & (proj.gender == gender)]
                .sort_values("cur_vdot", ascending=False).reset_index(drop=True))
    rank = int(cur_conf.index[cur_conf.team == team][0]) + 1
    n = len(cur_conf)
    fav = cur_conf.iloc[0]["team"]
    others_now = cur_conf[cur_conf.team != team]["cur_vdot"]
    win_now = float(others_now.max()) if len(others_now) else float(row["cur_vdot"])
    cur_vdot = float(row["cur_vdot"])
    act = lproject.coach_actions(frames, team, gender, prep=prep, proj=proj, qualify=QUAL)
    st.markdown(f"**{conf} standing now: #{rank} of {n}**"
                + ("  — you're the favorite." if rank == 1 else f"  (favorite: {fav})"))

    st.markdown("**Team fitness score (VDOT — higher = fitter)**")
    a1, a2, a3 = st.columns(3)
    a1.metric("Your team", f"{cur_vdot:.1f}")
    a2.metric(f"To win {conf}", f"{win_now:.1f}", f"{cur_vdot - win_now:+.1f}")
    a3.metric("To qualify nationals", f"{QUAL:.1f}", f"{cur_vdot - QUAL:+.1f}")

    st.markdown("**Incoming freshman class (VDOT)**")
    tr, qr = act["title"][2029]["recruit"], act["qualify_recruit"]
    b1, b2, b3 = st.columns(3)
    b1.metric("Your class avg", f"{cur_arr:.1f}",
              f"{int(row['class_size'])} freshmen/yr", delta_color="off")
    b2.metric(f"Recruit to win {conf}", f"{tr:.1f}" if tr else "—",
              f"+{tr - cur_arr:.1f} VDOT" if tr else "combo needed",
              delta_color="normal")
    b3.metric("Recruit to qualify", f"{qr:.1f}" if qr else "—",
              f"+{qr - cur_arr:.1f} VDOT" if qr else "combo needed",
              delta_color="normal")
    st.caption("VDOT is the course/distance-neutral fitness score (relative index; "
               "qualify bar is cross-validated). ‘To win’ = beat the strongest rival's "
               "projection; recruit targets develop over a full career. ~1 VDOT ≈ 6.5 s/5k.")

    st.markdown("**Your two goals** — where your top‑5 average needs to be:")
    st.markdown(f"- 🏆 **Win the {conf}** — beat the favorite (dashed line in chart)\n"
                f"- 🎟️ **Qualify for nationals** — top‑5 averaging **~{qual_time}** "
                "per runner at the regional")

    st.markdown("**Now adjust your plan** (drag to see the impact):")
    c1, c2 = st.columns(2)
    dA = c1.slider("🎯 Recruiting: freshmen faster than today (sec/5k)", 0, 40, 0, 5,
                   help="How much faster your incoming class arrives vs your recent norm") / SPV
    dev = c2.slider("📈 Training: extra improvement per year (sec/5k)", 0, 20, 0, 1,
                    help="On top of your program's recent year-over-year gains") / SPV

    years = list(range(2026, 2030))
    scen = lproject.project_scenario(frames, team, gender, arrival=cur_arr + dA,
                                     dev_boost=dev, prep=prep)
    others = proj[(proj.conference == conf) & (proj.gender == gender) & (proj.team != team)]
    title_bar = {y: float(others[f"proj_{y}"].max()) for y in years} if len(others) else {}

    # chart: seconds/runner from the qualifying line (0 = qualify)
    dfp = pd.DataFrame({"season": years,
                        "Your plan": [(scen[y] - QUAL) * SPV for y in years],
                        "If nothing changes": [(float(row[f"proj_{y}"]) - QUAL) * SPV for y in years]})
    if title_bar:
        dfp[f"Beat {conf} favorite"] = [(title_bar[y] - QUAL) * SPV for y in years]
    dfp["Qualify line"] = 0.0
    st.markdown("### 📈 Your projection, 2026–2029")
    long = dfp.melt("season", var_name="series", value_name="sec")
    fig = px.line(long, x="season", y="sec", color="series", markers=True)
    fig.update_yaxes(title="seconds per runner from qualifying (0 = you'd qualify)")
    fig.update_xaxes(title="season", dtick=1, tickformat="d")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Each line is your top‑5 average. The **0 line = the national‑"
               "qualifying level**; higher is fitter. **‘If nothing changes’** is your "
               "current path; **‘Your plan’** reflects the sliders above. The dashed "
               "conference line is the level needed to win your league.")

    fin = scen[2029]
    st.markdown("### Where your plan gets you (by 2029)")
    m1, m2 = st.columns(2)
    if title_bar:
        gt = (title_bar[2029] - fin) * SPV
        m1.metric(f"🏆 Win the {conf}", "YES ✅" if fin >= title_bar[2029] else "not yet",
                  f"{-gt:+.0f} sec/5k vs favorite")
    gq = (QUAL - fin) * SPV
    m2.metric("🎟️ Qualify nationals", "YES ✅" if fin >= QUAL else "not yet",
              f"{-gq:+.0f} sec/5k vs line")

    def rec(v):
        if v is None:
            return "not reachable on recruiting alone"
        return f"recruit freshmen ~**{(v - cur_arr) * SPV:.0f} sec/5k faster** than today"

    def dv(v):
        if v is None:
            return "not reachable on training alone"
        return f"have runners improve ~**{v * SPV:.0f} sec/5k more each year**"

    t29 = act["title"][2029]
    st.markdown("### 🧭 What to do")
    st.markdown(f"- **To win the {conf}:** {rec(t29['recruit'])}  — *or* {dv(t29['develop'])}.")
    st.markdown("- **To qualify for nationals:** this usually takes **both** — "
                f"{rec(act['qualify_recruit'])} **and** keep your runners improving. "
                "Nudge both sliders above to find the mix that crosses the qualify line.")
    st.caption("“If nothing changes” = your current recruiting + training rates. The "
               "recruiting numbers are approximate until high-school times are added; "
               "the goal times and the trend are measured from real meets.")


def render_readme():
    st.title("📖 How it works")
    st.markdown(
        "A plain‑language guide — **no math or stats background needed.** "
        "This tool helps you see where your cross country program stands and what "
        "it would take to **win your conference** and **qualify for nationals** over "
        "the next few years.")

    st.success("**Why trust it?** Its fitness ratings agreed with your **actual "
               "conference finishes 90% of the time** over the last decade (1,172 of "
               "1,304 team head‑to‑head matchups), and the national‑qualifying line "
               "was confirmed two independent ways.")

    st.subheader("Start here: the Coach Mode page")
    st.markdown(
        "**Coach Mode** (top of the sidebar) is the main page. It reads top to bottom:\n\n"
        "1. **Where your program stands today** — your team as of the end of the 2025 "
        "season, i.e. your starting point heading into 2026. You'll see a fitness "
        "score, your rank in the conference, and your incoming recruiting class.\n"
        "2. **Your two goals** — the fitness level (shown as a real race time) your "
        "top‑5 need to *win your conference* and to *qualify for nationals*.\n"
        "3. **Adjust your plan** — two sliders let you test *what if we recruit a bit "
        "faster* and *what if our runners improve a bit more each year*. Everything "
        "updates live.\n"
        "4. **What to do** — a plain recommendation for reaching each goal.")

    st.subheader("What the numbers mean")
    st.markdown(
        "- **Fitness score (VDOT):** one number for how fit a team is, that works "
        "across different courses and race distances. **Higher = fitter.** We also "
        "translate it into a real race time so it's tangible.\n"
        "- **Qualify for nationals:** your top‑5 need to average about **25:27 for 8k "
        "(men)** or **22:40 for 6k (women)** at the regional meet. That's the bar the "
        "last qualifying team has hit.\n"
        "- **Win your conference:** you need to beat the strongest projected team in "
        "your league (for the NCAC that's currently John Carroll).\n"
        "- **Recruiting number:** the fitness level your *incoming freshmen* arrive "
        "at. **Development:** how much your athletes improve each year they're with you.")

    st.subheader("How to read the projection graph")
    st.markdown(
        "- Each line is your **top‑5 average** over the next four seasons.\n"
        "- The **0 line is the national‑qualifying level** — at or above it means you'd "
        "qualify.\n"
        "- **‘If nothing changes’** is your current path; **‘Your plan’** shows the "
        "effect of the sliders; the **dashed conference line** is the level to win "
        "your league.\n"
        "- Lines often **dip in later years** — that just means your current seniors "
        "graduate and, at today's recruiting, aren't fully replaced. That's the whole "
        "point of the sliders: see what it takes to hold or climb.")

    st.subheader("What it can and can't do")
    st.markdown(
        "- ✅ Good for **big‑picture planning**: how much recruiting and development it "
        "takes to reach a goal.\n"
        "- ⚠️ It's a **projection, not a prediction** — it assumes your recruiting and "
        "training stay about the same *unless you move the sliders*.\n"
        "- ⚠️ It doesn't know about **injuries, transfers, or specific athletes**, and "
        "recruiting targets are **approximate** (they get sharper as we add more data).\n"
        "- ⚠️ The women's data is **thinner** than the men's, so treat those numbers as "
        "a rougher guide.")

    st.subheader("The other tabs (optional, more detailed)")
    st.markdown(
        "The remaining sidebar views are deeper dives — conference standings, national "
        "results, historical development, and the underlying ratings. **You don't need "
        "them to use Coach Mode**; explore only if you're curious. Use the **Time "
        "window** filter in the sidebar to focus those tables on the last 1/3/5 years.")

    st.info("Ready? Pick **Coach Mode** at the top of the left sidebar and choose your "
            "program.")


if __name__ == "__main__":
    main()
