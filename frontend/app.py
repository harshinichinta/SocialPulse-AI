"""Streamlit user interface; all analytics are requested from the FastAPI service."""

from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("SOCIALPULSE_API_URL", "http://127.0.0.1:8000").rstrip("/")
PAGES = [
    "Overview", "Dataset Explorer", "Sentiment Analysis", "Topic Discovery",
    "Emerging Trends", "Trend Forecasting", "Brand Intelligence",
    "Big Data Processing", "Model Evaluation", "Project Information",
]
st.set_page_config(page_title="SocialPulse AI", page_icon=None, layout="wide")
st.markdown("""
<style>
    .block-container { padding-top: 1.7rem; }
    [data-testid="stMetric"] { background: #f4f7fb; padding: 1rem; border-radius: .6rem; }
    h1, h2, h3 { color: #15324b; }
</style>
""", unsafe_allow_html=True)


def request_api(method: str, path: str, **kwargs):
    try:
        response = requests.request(method, f"{API_URL}{path}", timeout=90, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        message = exc.response.text if exc.response is not None else str(exc)
        st.error(f"Backend request failed: {message[:500]}")
        return None


def current_result():
    return st.session_state.get("analysis")


with st.sidebar:
    st.title("SocialPulse AI")
    st.caption("Explainable social media intelligence")
    page = st.radio("Workspace", PAGES, label_visibility="collapsed")
    st.divider()
    st.caption(f"API: {API_URL}")
    health = request_api("GET", "/health")
    st.caption("Backend connected" if health else "Backend unavailable")

st.title(page)
st.caption("Explore observed data. Model outputs are estimates and suggestions, not verified facts.")

if page == "Overview":
    uploaded = st.file_uploader("Upload a CSV dataset", type=["csv"], key="overview_upload")
    if uploaded:
        try:
            header = pd.read_csv(uploaded, nrows=0)
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
            st.error(f"Could not read CSV headers: {exc}")
            header = None
        if header is not None:
            columns = list(header.columns)
            defaults = {column.casefold(): column for column in columns}
            text_default = next((defaults[key] for key in ("text", "content", "tweet", "post")
                                 if key in defaults), columns[0])
            with st.form("dataset_mapping"):
                text_column = st.selectbox("Post text column", columns, index=columns.index(text_default))
                timestamp_choices = ["(none)"] + columns
                timestamp_default = next((defaults[key] for key in ("timestamp", "date", "created_at")
                                          if key in defaults), "(none)")
                timestamp_column = st.selectbox(
                    "Timestamp column (optional)", timestamp_choices,
                    index=timestamp_choices.index(timestamp_default),
                )
                platform_column = st.selectbox("Platform column (optional)", ["(none)"] + columns)
                brand_column = st.selectbox("Brand/topic column (optional)", ["(none)"] + columns)
                submit = st.form_submit_button("Analyze dataset", type="primary")
            if submit:
                uploaded.seek(0)
                files = {"file": (uploaded.name, uploaded.getvalue(), "text/csv")}
                data = {"text_column": text_column}
                if timestamp_column != "(none)":
                    data["timestamp_column"] = timestamp_column
                if platform_column != "(none)":
                    data["platform_column"] = platform_column
                if brand_column != "(none)":
                    data["brand_column"] = brand_column
                with st.spinner("Validating and analyzing the dataset..."):
                    result = request_api("POST", "/analyze/dataset", files=files, data=data)
                if result:
                    st.session_state["analysis"] = result
                    st.success(f"Analyzed {result['summary']['total_posts']:,} posts.")

    result = current_result()
    if result:
        summary = result["summary"]
        metrics = st.columns(4)
        metrics[0].metric("Posts analyzed", summary["total_posts"])
        metrics[1].metric("Positive", summary["sentiment_counts"].get("positive", 0))
        metrics[2].metric("Neutral", summary["sentiment_counts"].get("neutral", 0))
        metrics[3].metric("Negative", summary["sentiment_counts"].get("negative", 0))
        st.info(f"Processing: {result['analysis_mode']}. This is not a Hadoop execution.")
        distribution = pd.DataFrame(
            [{"Sentiment": label.title(), "Posts": count}
             for label, count in summary["sentiment_counts"].items()]
        )
        if not distribution.empty:
            st.plotly_chart(px.pie(distribution, names="Sentiment", values="Posts",
                                   color_discrete_sequence=["#2a9d8f", "#829ab1", "#e76f51"]),
                            use_container_width=True)
        timeline = pd.DataFrame(summary["sentiment_over_time"])
        if not timeline.empty:
            timeline = timeline.pivot(index="date", columns="sentiment", values="count").fillna(0)
            st.subheader("Sentiment over time")
            st.line_chart(timeline)
        hashtags = pd.DataFrame(summary["hashtags"])
        if not hashtags.empty:
            st.subheader("Frequently used hashtags")
            st.bar_chart(hashtags.set_index("hashtag")["count"])
        st.subheader("Recent analysis history")
        history = request_api("GET", "/analytics/history")
        if history and history["items"]:
            st.dataframe(pd.DataFrame(history["items"]), use_container_width=True)
    else:
        st.info("Upload a CSV to begin. No dashboard metrics are generated until data is analyzed.")

elif page == "Dataset Explorer":
    result = current_result()
    if not result:
        st.info("Upload and analyze a CSV from Overview first.")
    else:
        st.json(result["dataset"])
        data = pd.DataFrame(result["records"])
        sentiment_filter = st.multiselect("Filter sentiment", sorted(data["sentiment"].unique()))
        search = st.text_input("Search post text")
        filtered = data
        if sentiment_filter:
            filtered = filtered[filtered["sentiment"].isin(sentiment_filter)]
        if search:
            filtered = filtered[filtered["text"].str.contains(
                search, case=False, regex=False, na=False
            )]
        dates = pd.to_datetime(filtered["timestamp"], errors="coerce", utc=True)
        valid_dates = dates.dropna()
        if not valid_dates.empty:
            chosen_dates = st.date_input(
                "Date range", (valid_dates.min().date(), valid_dates.max().date())
            )
            if isinstance(chosen_dates, tuple) and len(chosen_dates) == 2:
                filtered = filtered[
                    dates.notna()
                    & (dates.dt.date >= chosen_dates[0])
                    & (dates.dt.date <= chosen_dates[1])
                ]
        st.dataframe(filtered, use_container_width=True, hide_index=True)
        st.download_button("Download analyzed data (CSV)", filtered.to_csv(index=False).encode(),
                           "socialpulse_analyzed.csv", "text/csv")

elif page == "Sentiment Analysis":
    text = st.text_area("Enter a post", max_chars=10_000)
    if st.button("Analyze sentiment", type="primary", disabled=not text.strip()):
        result = request_api("POST", "/predict/sentiment", json={"text": text})
        if result:
            st.metric("Predicted sentiment", result["sentiment"].title())
            st.caption(f"Baseline score: {result['confidence']} — not a calibrated probability.")
            st.json(result)
    if current_result():
        counts = current_result()["summary"]["sentiment_counts"]
        st.subheader("Dataset sentiment")
        st.bar_chart(pd.Series(counts, name="posts"))

elif page == "Topic Discovery":
    result = current_result()
    if result:
        st.caption(result["topics"]["method"])
        st.warning(result["topics"]["message"])
        topics = pd.DataFrame(result["topics"]["topics"])
        if not topics.empty:
            st.dataframe(topics, use_container_width=True, hide_index=True)
        keywords = pd.DataFrame(result["summary"]["keywords"])
        if not keywords.empty:
            st.bar_chart(keywords.set_index("keyword")["count"])
    else:
        st.info("Analyze a dataset first to discover topics.")

elif page == "Emerging Trends":
    result = current_result()
    if result:
        st.caption("Comparison uses the latest available timestamp and equal-sized adjacent windows.")
        trends = pd.DataFrame(result["trends"]["trends"])
        if trends.empty:
            st.info(result["trends"].get("message", "No topics met the threshold or timestamp requirements."))
        else:
            st.dataframe(trends, use_container_width=True, hide_index=True)
    else:
        st.info("Analyze a timestamped dataset first.")

elif page == "Trend Forecasting":
    result = current_result()
    topics = result["summary"]["keywords"] if result else []
    if not result:
        st.info("Analyze a dataset first. Forecasting needs at least three dated periods.")
    elif not result["dataset"]["timestamp_column"]:
        st.warning("A timestamp column is required to create historical time series.")
    else:
        choices = [item["keyword"] for item in topics]
        topic = st.selectbox("Keyword to forecast", choices)
        horizon = st.slider("Forecast periods", 1, 30, 7)
        if st.button("Create exploratory forecast"):
            frame = pd.DataFrame(result["records"])
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
            mask = frame["text"].str.contains(rf"\b{topic}\b", case=False, regex=True, na=False)
            series = (frame[mask].dropna(subset=["timestamp"]).set_index("timestamp")
                      .resample("D").size().rename("count").reset_index())
            points = [{"date": row.timestamp.date().isoformat(), "count": int(row.count)}
                      for row in series.itertuples()]
            forecast = request_api("POST", "/forecast",
                                   json={"topic": topic, "points": points, "horizon": horizon})
            if forecast:
                st.json(forecast["evaluation"])
                st.warning(forecast["warning"])
                observed = pd.DataFrame(forecast["history"]).assign(series="Observed")
                predicted = pd.DataFrame(forecast["forecast"]).rename(
                    columns={"predicted_count": "count"}).assign(series="Forecast")
                plot_data = pd.concat([observed[["date", "count", "series"]],
                                       predicted[["date", "count", "series"]]])
                st.plotly_chart(px.line(plot_data, x="date", y="count", color="series",
                                        markers=True), use_container_width=True)

elif page == "Brand Intelligence":
    result = current_result()
    if not result:
        st.info("Analyze a dataset containing brand or product mentions first.")
    else:
        brand_text = st.text_input("Brands, products, or topics (comma-separated)")
        data = pd.DataFrame(result["records"])
        brands = [brand.strip() for brand in brand_text.split(",") if brand.strip()]
        if brands:
            comparisons = []
            for brand in brands:
                text_matches = data["text"].str.contains(brand, case=False, regex=False, na=False)
                brand_matches = data["brand"].str.contains(brand, case=False, regex=False, na=False)
                subset = data[text_matches | brand_matches]
                for sentiment, count in subset["sentiment"].value_counts().items():
                    comparisons.append({"Brand/topic": brand, "Sentiment": sentiment, "Posts": count})
            comparison_frame = pd.DataFrame(comparisons)
            if not comparison_frame.empty:
                st.bar_chart(comparison_frame.pivot(
                    index="Brand/topic", columns="Sentiment", values="Posts"
                ).fillna(0))
                st.dataframe(comparison_frame, use_container_width=True, hide_index=True)
                st.metric("Matching mentions across entered terms",
                          sum(int(item["Posts"]) for item in comparisons))
                matched_mask = pd.Series(False, index=data.index)
                for brand in brands:
                    matched_mask |= (
                        data["text"].str.contains(brand, case=False, regex=False, na=False)
                        | data["brand"].str.contains(brand, case=False, regex=False, na=False)
                    )
                subset = data[matched_mask]
                st.dataframe(subset[["text", "timestamp", "sentiment", "platform"]],
                             use_container_width=True, hide_index=True)
                dated = subset.assign(
                    date=pd.to_datetime(subset["timestamp"], errors="coerce", utc=True)
                ).dropna(subset=["date"])
                if not dated.empty:
                    dated["date"] = dated["date"].dt.strftime("%Y-%m-%d")
                    trend = dated.groupby(["date", "sentiment"]).size().unstack(
                        fill_value=0
                    )
                    st.subheader("Matched sentiment over time")
                    st.line_chart(trend)
                left, right = st.columns(2)
                left.caption("Negative-matching examples (not verified complaints)")
                left.dataframe(subset[subset["sentiment"] == "negative"][["text"]].head(5),
                               hide_index=True)
                right.caption("Positive-matching examples (not verified praise)")
                right.dataframe(subset[subset["sentiment"] == "positive"][["text"]].head(5),
                                hide_index=True)
                if st.button("Suggest themes in matched posts", disabled=subset.empty):
                    themes = request_api(
                        "POST",
                        "/analyze/topics",
                        json={"texts": subset["text"].head(10).tolist()},
                    )
                    if themes:
                        st.caption(themes["message"])
                        st.dataframe(pd.DataFrame(themes["topics"]), hide_index=True)
            else:
                st.info("No matching posts found. Text matching does not establish product identity or opinion.")
        st.caption("Sentiment and keyword matching do not confirm that a mention refers to a specific product.")

elif page == "Big Data Processing":
    st.subheader("Choose the processing mode honestly")
    st.markdown("""
    **Current dashboard:** local, single-machine Pandas/scikit-learn analytics.
    **Distributed demonstration:** Hadoop Streaming MapReduce and Hive assets are provided separately;
    they require a configured Java, Hadoop and Hive environment. Their presence here does not mean a
    cluster is running.

    See the README for HDFS commands, Hadoop Streaming jobs, Hive setup, and validation steps.
    """)
    st.code("python bigdata/mapreduce/local_wordcount.py data/sample/socialpulse_sample.csv")

elif page == "Model Evaluation":
    st.subheader("Model and evaluation status")
    st.write("The built-in sentiment analyzer is a transparent lexicon baseline, not a trained model.")
    labeled_file = st.file_uploader("Optional labeled CSV (text and sentiment columns)", type=["csv"])
    if labeled_file:
        try:
            header = pd.read_csv(labeled_file, nrows=0)
            columns = list(header.columns)
            text_default = next((name for name in columns if name.casefold() in
                                 {"text", "content", "tweet", "post"}), columns[0])
            label_default = next((name for name in columns if name.casefold() in
                                  {"sentiment", "label", "target"}), columns[-1])
            with st.form("evaluation_mapping"):
                text_column = st.selectbox("Evaluation text column", columns,
                                           index=columns.index(text_default))
                label_column = st.selectbox("Reference label column", columns,
                                            index=columns.index(label_default))
                submit_evaluation = st.form_submit_button("Evaluate baseline")
            if submit_evaluation:
                response = request_api(
                    "POST",
                    "/evaluate/sentiment",
                    files={"file": (labeled_file.name, labeled_file.getvalue(), "text/csv")},
                    data={"text_column": text_column, "label_column": label_column},
                )
                if response:
                    st.metric("Accuracy on supplied labels", response["accuracy"])
                    st.caption(f"{response['examples']} labeled examples; {response['note']}")
                    report = pd.DataFrame(response["per_class"]).T
                    st.dataframe(report, use_container_width=True)
                    matrix = pd.DataFrame(response["confusion_matrix"],
                                           index=response["labels"], columns=response["labels"])
                    st.caption("Confusion matrix: rows are reference labels; columns are predictions.")
                    st.dataframe(matrix)
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
            st.error(f"Could not read labeled CSV headers: {exc}")
    else:
        st.warning("No accuracy, precision, recall, F1, or confusion matrix is reported without labeled test data.")
    st.write("Topic labels are unsupervised suggestions. Forecast evaluation is a time-ordered holdout.")
    st.write("Use the labeled-data guidance in docs/ACADEMIC_REPORT.md to run a meaningful evaluation.")

else:
    st.subheader("Project information")
    st.write("SocialPulse AI explores social text sentiment, topic suggestions, short-window volume changes, and baseline forecasts.")
    st.write("The application is a student project prototype. It does not identify authors or verify causal claims.")
    st.write("See README.md and docs/ for architecture, methodology, limitations, Hadoop workflow, and presentation notes.")
