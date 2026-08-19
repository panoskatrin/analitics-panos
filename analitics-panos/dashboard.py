"""User-friendly Streamlit dashboard for VTS meeting analytics.

Run with:

    streamlit run dashboard.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from vts_analytics_engine import VTSAnalyticsEngine, create_sample_meeting


DEFAULT_CSV_PATH = Path("realistic_meeting.csv")
MEETING_ID_COLUMNS = ("meeting_id", "meeting", "meeting_name", "session_id", "call_id")
PALETTE = ["#2563eb", "#f97316", "#16a34a", "#dc2626", "#7c3aed", "#0891b2", "#be123c"]


st.set_page_config(page_title="VTS Meeting Analytics", layout="wide")


def inject_css() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background: #f7fafc;
                color: #111827;
                font-size: 18px;
            }
            h1 {
                font-size: 2.6rem !important;
                font-weight: 800 !important;
                color: #0f172a;
                letter-spacing: 0;
            }
            h2 {
                font-size: 2rem !important;
                font-weight: 800 !important;
                color: #111827;
                letter-spacing: 0;
            }
            h3 {
                font-size: 1.45rem !important;
                font-weight: 800 !important;
                color: #1f2937;
                letter-spacing: 0;
            }
            [data-testid="stSidebar"] {
                background: #ffffff;
                border-right: 1px solid #e5e7eb;
                max-width: 310px;
            }
            [data-testid="stSidebar"] * {
                font-size: 1rem;
            }
            .metric-card {
                min-height: 150px;
                padding: 24px 20px;
                border-radius: 10px;
                color: #ffffff;
                font-weight: 800;
                text-align: center;
                box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.25);
            }
            .metric-card .metric-label {
                font-size: 1rem;
                line-height: 1.35;
                opacity: 0.96;
            }
            .metric-card .metric-value {
                margin-top: 14px;
                font-size: 2.35rem;
                line-height: 1;
            }
            .metric-good { background-color: #16a34a; }
            .metric-medium { background-color: #f59e0b; }
            .metric-bad { background-color: #dc2626; }
            .section-note {
                padding: 14px 16px;
                border-left: 5px solid #2563eb;
                background: #eff6ff;
                color: #1e3a8a;
                border-radius: 8px;
                font-size: 1.03rem;
            }
            .summary-box {
                padding: 18px 20px;
                background: #ffffff;
                border: 1px solid #dbe4ef;
                border-radius: 8px;
                box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
            }
            .summary-heading {
                color: #1d4ed8;
                font-weight: 800;
                font-size: 1.25rem;
                margin-bottom: 8px;
            }
            [data-testid="stDataFrame"] {
                font-size: 18px;
            }
            div[data-testid="stMetricValue"] {
                font-size: 2.1rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_status_class(value: float) -> str:
    if value >= 80:
        return "metric-good"
    if value >= 60:
        return "metric-medium"
    return "metric-bad"


def format_minutes(seconds: float) -> float:
    return round(float(seconds) / 60, 1)


def sentiment_marker_color(value: float) -> str:
    if value > 0:
        return "#16a34a"
    if value < 0:
        return "#dc2626"
    return "#f59e0b"


def prepare_speaker_table(speaker_stats: pd.DataFrame) -> pd.DataFrame:
    if speaker_stats.empty:
        return pd.DataFrame(
            columns=["Speaker", "Speaking Time (min)", "Percentage", "Number of Utterances"]
        )

    table = speaker_stats.copy()
    return pd.DataFrame(
        {
            "Speaker": table["speaker"],
            "Speaking Time (min)": table["total_speaking_time"].apply(format_minutes),
            "Percentage": table["speaking_time_pct"].apply(lambda value: f"{float(value):.1f}%"),
            "Number of Utterances": table["segment_count"].astype(int),
        }
    )


def metric_card(label: str, value: str, status_class: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card {status_class}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def load_source_dataframe() -> tuple[pd.DataFrame, str]:
    with st.sidebar:
        st.header("Data Source")
        uploaded = st.file_uploader("Upload transcript CSV", type=["csv"])
        local_path = st.text_input("CSV path", value=str(DEFAULT_CSV_PATH))
        st.caption("CSV columns should include speaker, start_time, end_time, and text.")

    if uploaded is not None:
        return pd.read_csv(uploaded), "Uploaded CSV"

    if local_path:
        path = Path(local_path)
        if path.exists():
            return pd.read_csv(path), str(path)

    if DEFAULT_CSV_PATH.exists():
        return pd.read_csv(DEFAULT_CSV_PATH), str(DEFAULT_CSV_PATH)

    return create_sample_meeting(), "Bundled sample meeting"


def select_meeting(df: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
    meeting_column = next((column for column in MEETING_ID_COLUMNS if column in df.columns), None)
    if not meeting_column:
        return df, None

    meetings = sorted(str(value) for value in df[meeting_column].dropna().unique())
    if not meetings:
        return df, None

    with st.sidebar:
        selected = st.selectbox("Meeting", meetings)

    return df[df[meeting_column].astype(str) == selected].copy(), selected


def run_analysis(df: pd.DataFrame) -> tuple[VTSAnalyticsEngine, dict[str, Any]]:
    engine = VTSAnalyticsEngine(df)
    return engine, engine.full_analysis()


def base_figure_layout(fig: go.Figure, title: str, x_title: str = "", y_title: str = "") -> go.Figure:
    fig.update_layout(
        title={"text": title, "font": {"size": 24}},
        font={"size": 18, "color": "#111827"},
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        xaxis_title=x_title,
        yaxis_title=y_title,
        margin={"l": 40, "r": 40, "t": 70, "b": 50},
        legend_title_text="",
    )
    fig.update_xaxes(title_font={"size": 18}, tickfont={"size": 16}, gridcolor="#e5e7eb")
    fig.update_yaxes(title_font={"size": 18}, tickfont={"size": 16}, gridcolor="#e5e7eb")
    return fig


def render_overview(results: dict[str, Any]) -> None:
    summary = results["summary"]
    quality = results["quality"]
    participation_balance = float(results["participation_balance"])
    quality_score = float(quality["score"])

    cols = st.columns(4)
    with cols[0]:
        metric_card(
            "Total Meeting Duration",
            f"{summary['total_meeting_duration'] / 60:.1f} min",
            metric_status_class(quality_score),
        )
    with cols[1]:
        metric_card("Number of Speakers", str(summary["unique_speakers"]), "metric-good")
    with cols[2]:
        metric_card(
            "Participation Balance Score",
            f"{participation_balance:.1f}",
            metric_status_class(participation_balance),
        )
    with cols[3]:
        metric_card("Meeting Quality Score", f"{quality_score:.1f}", metric_status_class(quality_score))

    st.markdown("### Quality Breakdown")
    breakdown = pd.DataFrame(
        [
            {"Metric": label.replace("_", " ").title(), "Score": round(float(score), 1)}
            for label, score in quality["breakdown"].items()
        ]
    )
    fig = px.bar(
        breakdown,
        x="Metric",
        y="Score",
        color="Score",
        color_continuous_scale=["#dc2626", "#f59e0b", "#16a34a"],
        range_color=[0, 100],
        text="Score",
    )
    fig.update_traces(textposition="outside")
    fig.update_yaxes(range=[0, 105])
    st.plotly_chart(base_figure_layout(fig, "Meeting Quality Components", "", "Score"), use_container_width=True)


def render_speaker_analysis(speaker_stats: pd.DataFrame) -> None:
    if speaker_stats.empty:
        st.info("No speaker data available.")
        return

    chart_df = speaker_stats.copy().sort_values("total_speaking_time", ascending=True)
    chart_df["speaking_minutes"] = chart_df["total_speaking_time"] / 60
    chart_df["label"] = chart_df["speaking_time_pct"].apply(lambda value: f"{float(value):.1f}%")

    fig = px.bar(
        chart_df,
        x="speaking_minutes",
        y="speaker",
        orientation="h",
        color="speaker",
        color_discrete_sequence=PALETTE,
        text="label",
        labels={"speaking_minutes": "Speaking Time (min)", "speaker": "Speaker"},
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    st.plotly_chart(
        base_figure_layout(fig, "Speaking Time per Speaker", "Speaking Time (min)", "Speaker"),
        use_container_width=True,
    )

    st.markdown("### Speaker Participation Table")
    st.dataframe(prepare_speaker_table(speaker_stats), use_container_width=True, hide_index=True)


def render_sentiment_timeline(sentiment_segments: pd.DataFrame) -> None:
    if sentiment_segments.empty:
        st.info("No sentiment timeline data available.")
        return

    timeline = sentiment_segments.copy()
    timeline["time_min"] = timeline["start_time"] / 60
    timeline["marker_color"] = timeline["polarity"].apply(sentiment_marker_color)

    fig = go.Figure()
    fig.add_hrect(y0=0.5, y1=1, fillcolor="#dcfce7", opacity=0.45, line_width=0)
    fig.add_hrect(y0=-0.5, y1=0.5, fillcolor="#fef9c3", opacity=0.40, line_width=0)
    fig.add_hrect(y0=-1, y1=-0.5, fillcolor="#fee2e2", opacity=0.45, line_width=0)
    fig.add_trace(
        go.Scatter(
            x=timeline["time_min"],
            y=timeline["polarity"],
            mode="lines",
            line={"color": "#2563eb", "width": 3, "shape": "spline"},
            name="Sentiment",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=timeline["time_min"],
            y=timeline["polarity"],
            mode="markers",
            marker={
                "size": 10,
                "color": timeline["marker_color"],
                "line": {"color": "#ffffff", "width": 1.5},
            },
            customdata=timeline[["speaker", "text", "sentiment_category"]],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Time: %{x:.1f} min<br>"
                "Sentiment: %{y:.2f}<br>"
                "Category: %{customdata[2]}<br>"
                "%{customdata[1]}<extra></extra>"
            ),
            name="Segments",
        )
    )
    for y_value in [0, 0.5, -0.5]:
        fig.add_hline(y=y_value, line_dash="dash", line_color="#64748b", opacity=0.8)
    fig.update_yaxes(range=[-1, 1], tickmode="array", tickvals=[-1, 0, 1], ticktext=["-1", "0", "+1"])
    st.plotly_chart(
        base_figure_layout(fig, "Sentiment Over Time", "Time (minutes)", "Sentiment Score"),
        use_container_width=True,
    )


def render_language_detection(results: dict[str, Any]) -> None:
    language_distribution = pd.DataFrame(results["languages"]["distribution"])
    if language_distribution.empty:
        st.info("No language data available.")
        return

    pie = px.pie(
        language_distribution,
        values="segments",
        names="language_name",
        color_discrete_sequence=PALETTE,
        hole=0.25,
    )
    pie.update_traces(textposition="inside", textinfo="label+percent", textfont_size=18)
    st.plotly_chart(base_figure_layout(pie, "Language Distribution"), use_container_width=True)

    table = language_distribution[["language_name", "segments", "segment_pct", "duration_pct"]].copy()
    table.columns = ["Language", "Segments", "Segment Percentage", "Duration Percentage"]
    table["Segment Percentage"] = table["Segment Percentage"].map(lambda value: f"{float(value):.1f}%")
    table["Duration Percentage"] = table["Duration Percentage"].map(lambda value: f"{float(value):.1f}%")
    st.dataframe(table, use_container_width=True, hide_index=True)

    translation_metrics = results.get("translation_quality") or results.get("translation_quality_metrics")
    if translation_metrics:
        st.markdown("### Translation Quality Metrics")
        metrics_df = pd.DataFrame(
            [{"Metric": key.replace("_", " ").title(), "Score": value} for key, value in translation_metrics.items()]
        )
        fig = px.bar(metrics_df, x="Metric", y="Score", color="Metric", color_discrete_sequence=PALETTE, text="Score")
        fig.update_traces(textposition="outside")
        st.plotly_chart(base_figure_layout(fig, "Translation Quality", "", "Score"), use_container_width=True)


def render_summary_actions(results: dict[str, Any]) -> None:
    summary_text = results.get("ai_summary") or results.get("summary_text")
    decisions_actions = results.get("decisions_and_actions", {})
    decisions = decisions_actions.get("decisions", [])
    actions = decisions_actions.get("action_items", [])

    if summary_text:
        st.markdown(
            f"""
            <div class="summary-box">
                <div class="summary-heading">AI Summary</div>
                {summary_text}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="section-note">No AI-generated summary was found in this analysis output.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Decisions")
    if decisions:
        for item in decisions:
            st.markdown(f"- **{item.get('speaker', 'Unknown')}**: {item.get('text', '')}")
    else:
        st.info("No decisions detected.")

    st.markdown("### Action Items")
    if actions:
        for index, item in enumerate(actions, start=1):
            label = f"{item.get('speaker', 'Unknown')}: {item.get('text', '')}"
            st.checkbox(label, key=f"action_item_{index}")
    else:
        st.info("No action items detected.")


def main() -> None:
    inject_css()
    st.title("VTS Meeting Analytics Dashboard")

    try:
        source_df, source_label = load_source_dataframe()
        selected_df, selected_meeting = select_meeting(source_df)
        engine, results = run_analysis(selected_df)
    except Exception as exc:
        st.error(f"Unable to analyze transcript: {exc}")
        return

    with st.sidebar:
        st.divider()
        st.caption(f"Loaded from: {source_label}")
        if selected_meeting:
            st.caption(f"Selected meeting: {selected_meeting}")
        st.download_button(
            "Download analyzed CSV",
            data=engine.df.to_csv(index=False).encode("utf-8"),
            file_name="analyzed_transcript.csv",
            mime="text/csv",
        )
        st.download_button(
            "Download results JSON",
            data=json.dumps(results, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name="meeting_analytics.json",
            mime="application/json",
        )

    speaker_stats = pd.DataFrame(results["speakers"]["stats"])
    sentiment_segments = pd.DataFrame(results["sentiment"]["segments"])

    tabs = st.tabs(
        [
            "Overview",
            "Speaker Analysis",
            "Sentiment Timeline",
            "Language Detection",
            "AI Summary & Actions",
        ]
    )

    with tabs[0]:
        render_overview(results)
    with tabs[1]:
        render_speaker_analysis(speaker_stats)
    with tabs[2]:
        render_sentiment_timeline(sentiment_segments)
    with tabs[3]:
        render_language_detection(results)
    with tabs[4]:
        render_summary_actions(results)


if __name__ == "__main__":
    main()
