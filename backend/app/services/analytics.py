"""Local analytics primitives used by the API and the dashboard."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
import io
import json
import re
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

POSITIVE_WORDS = {
    "amazing", "awesome", "best", "brilliant", "delightful", "enjoy", "excellent",
    "fantastic", "good", "great", "happy", "love", "loved", "lovely", "nice",
    "perfect", "recommend", "thanks", "thank", "useful", "wonderful",
}
NEGATIVE_WORDS = {
    "annoying", "awful", "bad", "broken", "complaint", "delay", "disappointed",
    "disappointing", "hate", "hated", "issue", "late", "poor", "problem", "refund",
    "slow", "terrible", "unhappy", "worse", "worst",
}
STOP_WORDS = set(ENGLISH_STOP_WORDS) | {
    "amp", "http", "https", "www", "rt", "im", "ive", "youre", "thats",
}
TOKEN_RE = re.compile(r"[a-z][a-z0-9']{1,}")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"(?<!\w)@\w+")
HASHTAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_]+)")
MAX_TEXT_LENGTH = 10_000


def preprocess_text(text: Any) -> str:
    """Normalize social text without requiring an external language model."""
    if text is None or pd.isna(text):
        return ""
    value = URL_RE.sub(" ", str(text))
    value = MENTION_RE.sub(" ", value)
    value = value.replace("#", "")
    return " ".join(TOKEN_RE.findall(value.lower()))


def sentiment_prediction(text: str) -> dict[str, Any]:
    """Return a transparent lexicon baseline; scores are not calibrated probabilities."""
    tokens = preprocess_text(text).split()
    positive = sum(token in POSITIVE_WORDS for token in tokens)
    negative = sum(token in NEGATIVE_WORDS for token in tokens)
    if positive > negative:
        label = "positive"
    elif negative > positive:
        label = "negative"
    else:
        label = "neutral"

    evidence = positive + negative
    if evidence == 0:
        scores = {"positive": 0.25, "negative": 0.25, "neutral": 0.5}
    elif positive == negative:
        scores = {"positive": 0.25, "negative": 0.25, "neutral": 0.5}
    else:
        denominator = evidence + 1
        scores = {
            "positive": round((positive + (0.5 if label == "positive" else 0)) / denominator, 4),
            "negative": round((negative + (0.5 if label == "negative" else 0)) / denominator, 4),
            "neutral": round(0.5 / denominator, 4),
        }
    return {
        "text": text,
        "processed_text": " ".join(tokens),
        "sentiment": label,
        "class_scores": scores,
        "confidence": round(scores[label], 4),
        "model": {
            "name": "SocialPulse lexicon baseline",
            "version": "1.0",
            "type": "rule-based baseline",
            "score_note": "Scores reflect matched-word evidence; they are not calibrated probabilities.",
        },
    }


def load_csv_dataset(
    content: bytes,
    text_column: str | None = None,
    timestamp_column: str | None = None,
    platform_column: str | None = None,
    brand_column: str | None = None,
    max_rows: int = 5000,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Read and validate a bounded CSV, returning normalized records and import stats."""
    encoding = "utf-8-sig"
    try:
        frame = pd.read_csv(io.BytesIO(content), encoding=encoding)
    except UnicodeDecodeError:
        encoding = "cp1252"
        try:
            frame = pd.read_csv(io.BytesIO(content), encoding=encoding)
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
            raise ValueError(f"Could not parse the CSV file: {exc}") from exc
    except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
        raise ValueError(f"Could not parse the CSV file: {exc}") from exc
    if frame.empty:
        raise ValueError("The CSV contains no data rows.")
    if len(frame) > max_rows:
        raise ValueError(f"The CSV exceeds the {max_rows:,}-row limit.")
    if not len(frame.columns):
        raise ValueError("The CSV has no columns.")
    frame.columns = [str(column).strip() for column in frame.columns]

    if text_column is None:
        candidates = {column.casefold(): column for column in frame.columns}
        text_column = next(
            (candidates[name] for name in ("text", "content", "tweet", "post", "message")
             if name in candidates),
            None,
        )
    if text_column not in frame.columns:
        raise ValueError("Choose a text column that exists in the uploaded CSV.")
    if timestamp_column and timestamp_column not in frame.columns:
        raise ValueError("The selected timestamp column does not exist in the uploaded CSV.")
    if platform_column and platform_column not in frame.columns:
        raise ValueError("The selected platform column does not exist in the uploaded CSV.")
    if brand_column and brand_column not in frame.columns:
        raise ValueError("The selected brand or topic column does not exist in the uploaded CSV.")

    raw_count = len(frame)
    text = frame[text_column].fillna("").astype(str).str.strip()
    if text.str.len().gt(MAX_TEXT_LENGTH).any():
        raise ValueError(f"Post text cannot exceed {MAX_TEXT_LENGTH:,} characters.")
    nonempty = text.ne("")
    frame = frame.loc[nonempty].copy()
    frame["text"] = text.loc[nonempty]
    frame["processed_text"] = frame["text"].map(preprocess_text)
    frame["_dedup_key"] = frame["text"].str.casefold().str.replace(r"\s+", " ", regex=True)
    before_dedup = len(frame)
    frame = frame.drop_duplicates(subset=["_dedup_key"], keep="first").drop(
        columns=["_dedup_key"]
    ).copy()
    duplicates = before_dedup - len(frame)
    if timestamp_column:
        parsed = pd.to_datetime(frame[timestamp_column], errors="coerce", utc=True)
        frame["timestamp"] = parsed
    else:
        frame["timestamp"] = pd.NaT
    if platform_column:
        frame["platform"] = frame[platform_column].fillna("").astype(str).str.strip()
    else:
        frame["platform"] = ""
    if brand_column:
        frame["brand"] = frame[brand_column].fillna("").astype(str).str.strip()
    else:
        frame["brand"] = ""
    if frame.empty:
        raise ValueError("No non-empty post text remained after cleaning.")

    frame["sentiment"] = frame["text"].map(lambda value: sentiment_prediction(value)["sentiment"])
    stats = {
        "rows_received": raw_count,
        "rows_analyzed": len(frame),
        "empty_text_rows_removed": raw_count - int(nonempty.sum()),
        "duplicate_text_rows_removed": duplicates,
        "invalid_timestamps": int(frame["timestamp"].isna().sum()) if timestamp_column else 0,
        "text_column": text_column,
        "timestamp_column": timestamp_column,
        "platform_column": platform_column,
        "brand_column": brand_column,
        "encoding": encoding,
        "platforms": sorted(value for value in frame["platform"].unique() if value),
    }
    return frame.reset_index(drop=True), stats


def load_json_dataset(
    content: bytes,
    text_column: str | None = None,
    timestamp_column: str | None = None,
    platform_column: str | None = None,
    brand_column: str | None = None,
    max_rows: int = 5000,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load a JSON array or an object containing a records/posts/data array."""
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not parse the JSON file: {exc}") from exc
    if isinstance(payload, dict):
        payload = next(
            (payload[key] for key in ("records", "posts", "data") if key in payload),
            [payload],
        )
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise ValueError("JSON must contain an array of objects or an object with a records array.")
    if len(payload) > max_rows:
        raise ValueError(f"The JSON exceeds the {max_rows:,}-row limit.")
    if not payload:
        raise ValueError("The JSON contains no data rows.")
    csv_content = pd.DataFrame.from_records(payload).to_csv(index=False).encode("utf-8")
    frame, stats = load_csv_dataset(
        csv_content,
        text_column=text_column,
        timestamp_column=timestamp_column,
        platform_column=platform_column,
        brand_column=brand_column,
        max_rows=max_rows,
    )
    stats["encoding"] = "utf-8 JSON"
    stats["format"] = "json"
    return frame, stats


def load_labeled_csv(
    content: bytes, text_column: str, label_column: str, max_rows: int = 5000
) -> tuple[list[str], list[str]]:
    """Read a bounded evaluation CSV and discard rows without text or a reference label."""
    try:
        frame = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            frame = pd.read_csv(io.BytesIO(content), encoding="cp1252")
        except (UnicodeDecodeError, pd.errors.ParserError, ValueError) as exc:
            raise ValueError(f"Could not parse the labeled CSV file: {exc}") from exc
    except (pd.errors.ParserError, ValueError) as exc:
        raise ValueError(f"Could not parse the labeled CSV file: {exc}") from exc
    if frame.empty:
        raise ValueError("The labeled CSV contains no data rows.")
    if len(frame) > max_rows:
        raise ValueError(f"The labeled CSV exceeds the {max_rows:,}-row limit.")
    frame.columns = [str(column).strip() for column in frame.columns]
    if text_column not in frame.columns or label_column not in frame.columns:
        raise ValueError("Select existing text and label columns.")
    selected = frame[[text_column, label_column]].dropna()
    selected[text_column] = selected[text_column].astype(str).str.strip()
    selected[label_column] = selected[label_column].astype(str).str.strip()
    if selected[text_column].str.len().gt(MAX_TEXT_LENGTH).any():
        raise ValueError(f"Post text cannot exceed {MAX_TEXT_LENGTH:,} characters.")
    selected = selected[selected[text_column].ne("") & selected[label_column].ne("")]
    if selected.empty:
        raise ValueError("No rows with both text and a reference label were found.")
    return selected[text_column].tolist(), selected[label_column].tolist()


def extract_keywords(texts: list[str], limit: int = 15) -> list[dict[str, Any]]:
    words = Counter(
        token for text in texts for token in TOKEN_RE.findall(preprocess_text(text))
        if token not in STOP_WORDS and len(token) > 2
    )
    return [{"keyword": word, "count": count} for word, count in words.most_common(limit)]


def _umass_coherence(topic_terms: list[str], documents: list[set[str]]) -> float | None:
    if len(topic_terms) < 2:
        return None
    document_counts = Counter(
        term for document in documents for term in document if term in topic_terms
    )
    scores = []
    for later_index, later in enumerate(topic_terms[1:], start=1):
        later_documents = document_counts[later]
        if not later_documents:
            continue
        for earlier in topic_terms[:later_index]:
            cooccurrences = sum(earlier in document and later in document for document in documents)
            scores.append(np.log((cooccurrences + 1) / later_documents))
    return round(float(np.mean(scores)), 4) if scores else None


def discover_topics(
    texts: list[str],
    max_topics: int = 5,
    sentiments: list[str] | None = None,
) -> dict[str, Any]:
    clean = [preprocess_text(text) for text in texts if preprocess_text(text)]
    if not clean:
        return {"topics": [], "method": "TF-IDF + NMF", "message": "No text to analyze."}
    keywords = extract_keywords(clean, 20)
    if len(clean) < 3 or len(keywords) < 2:
        selected_sentiments = sentiments or [sentiment_prediction(text)["sentiment"] for text in texts]
        sentiment_counts = Counter(selected_sentiments)
        return {
            "topics": [{"topic_id": 0, "label": " ".join(item["keyword"] for item in keywords[:3])
                        or "insufficient text", "mentions": len(clean),
                        "terms": [item["keyword"] for item in keywords[:5]],
                        "sentiment_distribution": dict(sentiment_counts),
                        "representative_posts": clean[:3],
                        "coherence": None}],
            "method": "frequency-based small-sample fallback",
            "message": "Topic modeling needs more varied text; this is a frequency-based suggestion.",
        }
    vectorizer = TfidfVectorizer(stop_words=list(STOP_WORDS), max_features=1000, min_df=1)
    matrix = vectorizer.fit_transform(clean)
    topic_count = min(max_topics, len(clean), matrix.shape[1])
    if topic_count < 2:
        return {
            "topics": [{"topic_id": 0, "label": " ".join(item["keyword"] for item in keywords[:3]),
                        "mentions": len(clean), "terms": [item["keyword"] for item in keywords[:5]],
                        "sentiment_distribution": {}, "representative_posts": clean[:3],
                        "coherence": None}],
            "method": "frequency-based small-sample fallback",
            "message": "There are too few distinct terms to fit topic components.",
        }
    model = NMF(
        n_components=topic_count, init="nndsvda", random_state=42, max_iter=400,
    )
    document_topic = model.fit_transform(matrix)
    assignments = document_topic.argmax(axis=1)
    terms = np.asarray(vectorizer.get_feature_names_out())
    aligned_sentiments = sentiments or [
        sentiment_prediction(text)["sentiment"] for text in texts
    ]
    if len(aligned_sentiments) != len(texts):
        raise ValueError("Sentiment labels must align one-to-one with topic texts.")
    selected_sentiments = [
        sentiment for text, sentiment in zip(texts, aligned_sentiments)
        if preprocess_text(text)
    ]
    topics = []
    for topic_id, weights in enumerate(model.components_):
        top_indices = np.argsort(weights)[-5:][::-1]
        top_terms = terms[top_indices].tolist()
        member_indices = np.flatnonzero(assignments == topic_id)
        mentions = int(len(member_indices))
        if mentions:
            sentiment_distribution = Counter(
                selected_sentiments[index] for index in member_indices
            )
            representative_indices = sorted(
                member_indices,
                key=lambda index: document_topic[index, topic_id],
                reverse=True,
            )[:3]
            topics.append({
                "topic_id": topic_id,
                "label": ", ".join(top_terms[:3]),
                "mentions": mentions,
                "terms": top_terms,
                "sentiment_distribution": dict(sentiment_distribution),
                "representative_posts": [texts[index][:240] for index in representative_indices],
                "coherence": _umass_coherence(
                    top_terms, [set(document.split()) for document in clean]
                ),
            })
    topics.sort(key=lambda item: item["mentions"], reverse=True)
    return {
        "topics": topics,
        "method": "TF-IDF + non-negative matrix factorization (NMF)",
        "quality_metric": "UMass coherence; higher (less negative) is better, not a validation score",
        "message": "Topic names are generated from top terms; inspect representative posts before interpretation.",
    }


def detect_trends(
    records: list[dict[str, Any]],
    window_days: int = 7,
    min_mentions: int = 2,
    previous_minimum: int = 3,
) -> dict[str, Any]:
    dated = []
    for row in records:
        text = str(row.get("text") or "")
        timestamp = pd.to_datetime(row.get("timestamp"), errors="coerce", utc=True)
        if pd.isna(timestamp):
            continue
        tokens = {token for token in preprocess_text(text).split()
                  if token not in STOP_WORDS and len(token) > 2}
        dated.extend((timestamp, token, str(row.get("sentiment") or
                                             sentiment_prediction(text)["sentiment"]), text)
                     for token in tokens)
    if not dated:
        return {"trends": [], "message": "Valid timestamps are required for trend detection."}
    latest = max(item[0] for item in dated)
    period_end = latest.normalize() + timedelta(days=1)
    current_start = period_end - timedelta(days=window_days)
    previous_start = current_start - timedelta(days=window_days)
    counts: dict[str, Counter] = {}
    sentiments: dict[str, Counter] = {}
    representatives: dict[str, list[str]] = {}
    related_terms: dict[str, Counter] = {}
    for timestamp, token, sentiment, source_text in dated:
        if previous_start <= timestamp < current_start:
            counts.setdefault(token, Counter())["previous"] += 1
        elif current_start <= timestamp < period_end:
            counts.setdefault(token, Counter())["current"] += 1
            sentiments.setdefault(token, Counter())[sentiment] += 1
            samples = representatives.setdefault(token, [])
            if source_text and source_text not in samples and len(samples) < 3:
                samples.append(source_text[:240])
            related_terms.setdefault(token, Counter()).update(
                other for other in preprocess_text(source_text).split()
                if other != token and other not in STOP_WORDS
            )

    trends = []
    for token, values in counts.items():
        current, previous = values["current"], values["previous"]
        if current < min_mentions or current <= previous:
            continue
        growth = round((current - previous) / previous * 100, 1) if previous >= previous_minimum else None
        absolute_change = current - previous
        score = round(float(np.log1p(current) * absolute_change / max(previous, 1)), 4)
        trends.append({
            "topic": token,
            "current_mentions": current,
            "previous_mentions": previous,
            "absolute_change": absolute_change,
            "growth_percent": growth,
            "rank_score": score,
            "sentiment_distribution": dict(sentiments.get(token, {})),
            "keywords": [word for word, _ in related_terms.get(token, Counter()).most_common(5)],
            "representative_posts": representatives.get(token, []),
            "period_start": current_start.date().isoformat(),
            "period_end": (period_end - timedelta(days=1)).date().isoformat(),
            "window_days": window_days,
            "reason": (
                f"{current} posts in the latest {window_days} calendar days; "
                f"previous window {previous}; absolute change {absolute_change}. "
                + (f"Growth {growth}%." if growth is not None
                   else "Percentage growth withheld because the prior count is below the stability threshold.")
            ),
            "score_method": "log(1 + current mentions) × absolute change / max(previous mentions, 1)",
            "limitation": "A short-window volume increase is not evidence of a durable long-term trend.",
        })
    trends.sort(key=lambda item: (item["rank_score"], item["current_mentions"]), reverse=True)
    return {
        "trends": trends[:30],
        "window_days": window_days,
        "min_mentions": min_mentions,
        "score_method": "log(1 + current mentions) × absolute change / max(previous mentions, 1)",
        "significance": "No statistical significance is claimed; records may be synthetic or non-independent.",
    }


def _holt_damped_forecast(values: np.ndarray, horizon: int) -> np.ndarray:
    level = float(values[0])
    trend = float(values[1] - values[0]) if len(values) > 1 else 0.0
    alpha, beta, damping = 0.5, 0.2, 0.8
    for observed in values[1:]:
        previous_level = level
        level = alpha * float(observed) + (1 - alpha) * (level + damping * trend)
        trend = beta * (level - previous_level) + (1 - beta) * damping * trend
    return np.asarray([
        max(0.0, level + sum(damping ** step * trend for step in range(1, index + 1)))
        for index in range(1, horizon + 1)
    ])


def forecast_series(
    points: list[dict[str, Any]], horizon: int = 7
) -> dict[str, Any]:
    if not 1 <= horizon <= 30:
        raise ValueError("Forecast horizon must be between 1 and 30 periods.")
    frame = pd.DataFrame(points)
    if not {"date", "count"}.issubset(frame.columns):
        raise ValueError("Each history point must contain date and count.")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", utc=True)
    frame["count"] = pd.to_numeric(frame["count"], errors="coerce")
    frame = frame.dropna(subset=["date", "count"]).sort_values("date")
    if not np.isfinite(frame["count"].to_numpy(dtype=float)).all():
        raise ValueError("Counts must be finite numbers.")
    frame["date"] = frame["date"].dt.floor("D")
    frame = frame.groupby("date", as_index=False)["count"].sum()
    if (frame["count"] < 0).any():
        raise ValueError("Counts cannot be negative.")
    if frame.empty:
        raise ValueError("At least 14 daily periods are required to forecast.")
    daily_dates = pd.date_range(frame["date"].min(), frame["date"].max(), freq="D", tz="UTC")
    frame = (
        frame.set_index("date").reindex(daily_dates, fill_value=0)
        .rename_axis("date").reset_index()
    )
    if len(frame) < 14:
        raise ValueError(
            f"At least 14 consecutive daily periods are required to forecast; found {len(frame)}."
        )

    values = frame["count"].to_numpy(dtype=float)
    holdout = max(1, min(int(round(len(values) * 0.2)), 14))
    train_values = values[:-holdout]
    test_values = values[-holdout:]
    if len(train_values) >= 14:
        selection_periods = max(3, min(len(train_values) // 4, 7))
        selection_train = train_values[:-selection_periods]
        selection_test = train_values[-selection_periods:]
        selection_predictions = {
            "last_value_baseline": np.full(selection_periods, selection_train[-1], dtype=float),
            "holt_damped_trend": _holt_damped_forecast(selection_train, selection_periods),
        }
        selected_model = min(
            selection_predictions,
            key=lambda name: float(np.sqrt(np.mean((selection_test - selection_predictions[name]) ** 2))),
        )
        selection_method = "Earlier chronological validation split within training data."
    else:
        selected_model = "last_value_baseline"
        selection_method = "Holt model not selected: fewer than 14 training days for an inner validation split."
    baseline_prediction = np.full(holdout, train_values[-1], dtype=float)
    holt_prediction = _holt_damped_forecast(train_values, holdout)
    model_errors = {
        "last_value_baseline": {
            "mae": float(np.mean(np.abs(test_values - baseline_prediction))),
            "rmse": float(np.sqrt(np.mean((test_values - baseline_prediction) ** 2))),
        },
        "holt_damped_trend": {
            "mae": float(np.mean(np.abs(test_values - holt_prediction))),
            "rmse": float(np.sqrt(np.mean((test_values - holt_prediction) ** 2))),
        },
    }
    test_prediction = (
        holt_prediction if selected_model == "holt_damped_trend" else baseline_prediction
    )
    mae = model_errors[selected_model]["mae"]
    rmse = model_errors[selected_model]["rmse"]
    future_values = (
        _holt_damped_forecast(values, horizon)
        if selected_model == "holt_damped_trend"
        else np.full(horizon, values[-1], dtype=float)
    )
    absolute_errors = np.abs(test_values - test_prediction)
    interval_error = (
        float(np.quantile(absolute_errors, 0.8)) if holdout >= 10 else None
    )
    last_date = frame["date"].max()
    forecasts = []
    for index, value in enumerate(future_values, start=1):
        date = last_date + pd.Timedelta(days=index)
        forecasts.append({
            "date": date.date().isoformat(),
            "predicted_count": round(float(value), 2),
            "lower_bound": (
                round(max(0.0, float(value) - interval_error), 2)
                if interval_error is not None else None
            ),
            "upper_bound": (
                round(float(value) + interval_error, 2)
                if interval_error is not None else None
            ),
        })
    return {
        "history": [{"date": row.date.date().isoformat(), "count": float(row.count)}
                    for row in frame.itertuples()],
        "holdout_predictions": [
            {
                "date": frame.iloc[len(train_values) + index]["date"].date().isoformat(),
                "actual": float(actual),
                "predicted": round(float(predicted), 2),
            }
            for index, (actual, predicted) in enumerate(zip(test_values, test_prediction))
        ],
        "forecast": forecasts,
        "model": "Holt damped trend" if selected_model == "holt_damped_trend" else "last-value baseline",
        "evaluation": {
            "holdout_periods": holdout,
            "mae": round(mae, 3),
            "rmse": round(rmse, 3),
            "models": {
                name: {metric: round(value, 3) for metric, value in metrics.items()}
                for name, metrics in model_errors.items()
            },
            "split": "Chronological outer holdout; selected model was chosen using training-only validation.",
            "selection_method": selection_method,
        },
        "interval_method": (
            f"80th percentile of {holdout} absolute holdout errors; empirical band, not a calibrated confidence interval."
            if interval_error is not None else
            "Omitted: fewer than 10 holdout errors do not support a useful empirical interval."
        ),
        "warning": "Exploratory daily-count forecast; model choice and error reflect only this short input series.",
    }


def analyze_frame(frame: pd.DataFrame, stats: dict[str, Any]) -> dict[str, Any]:
    texts = frame["text"].astype(str).tolist()
    sentiment_counts = frame["sentiment"].value_counts().to_dict()
    topics = discover_topics(texts, sentiments=frame["sentiment"].astype(str).tolist())
    keyword_counts = extract_keywords(texts)
    hashtag_counts = Counter(
        hashtag.casefold()
        for text in texts
        for hashtag in HASHTAG_RE.findall(text)
    )
    dated_records = [
        {"text": row.text, "timestamp": row.timestamp, "sentiment": row.sentiment}
        for row in frame.itertuples()
    ]
    trends = detect_trends(dated_records)
    records = []
    for index, row in enumerate(frame.itertuples(), start=1):
        prediction = sentiment_prediction(row.text)
        supplied_id = getattr(row, "post_id", None)
        post_id = (
            str(supplied_id) if supplied_id is not None and not pd.isna(supplied_id)
            and str(supplied_id).strip() else f"POST-{index:06d}"
        )
        records.append({
            "post_id": post_id,
            "text": row.text,
            "processed_text": row.processed_text,
            "timestamp": row.timestamp.isoformat() if not pd.isna(row.timestamp) else None,
            "platform": row.platform,
            "brand": row.brand,
            "sentiment": row.sentiment,
            "sentiment_confidence": prediction["confidence"],
            "sentiment_scores": prediction["class_scores"],
        })
    sentiment_over_time = []
    dated_frame = frame.dropna(subset=["timestamp"]).copy()
    if not dated_frame.empty:
        dated_frame["date"] = dated_frame["timestamp"].dt.strftime("%Y-%m-%d")
        sentiment_over_time = [
            {"date": date, "sentiment": sentiment, "count": int(count)}
            for (date, sentiment), count in (
                dated_frame.groupby(["date", "sentiment"], observed=True).size().items()
            )
        ]
    result = {
        "dataset": stats,
        "summary": {
            "total_posts": len(frame),
            "sentiment_counts": {key: int(value) for key, value in sentiment_counts.items()},
            "sentiment_model": {
                "name": "SocialPulse lexicon baseline",
                "version": "1.0",
                "type": "rule-based baseline",
            },
            "keywords": keyword_counts,
            "hashtags": [{"hashtag": tag, "count": count}
                         for tag, count in hashtag_counts.most_common(15)],
            "sentiment_over_time": sentiment_over_time,
        },
        "topics": topics,
        "trends": trends,
        "records": records,
        "analysis_mode": "local single-machine processing",
        "source": {
            "name": "Imported dataset",
            "type": "imported",
            "status": "loaded",
            "is_live": False,
        },
        "insights": [],
        "brand_comparison": compare_brands(records),
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    result["insights"] = [
        {
            "title": f"More recent mentions of “{trend['topic']}”",
            "topic": trend["topic"],
            "evidence": trend["reason"],
            "period": f"{trend['period_start']} to {trend['period_end']}",
            "mentions": trend["current_mentions"],
            "previous_mentions": trend["previous_mentions"],
            "growth_percent": trend["growth_percent"],
            "sentiment_distribution": trend["sentiment_distribution"],
            "keywords": trend["keywords"],
            "representative_posts": trend["representative_posts"],
            "limitation": trend["limitation"],
            "recommendation": "Review the linked records and validate this signal against an independent data source.",
        }
        for trend in trends["trends"]
        if trend["current_mentions"] >= 8
    ]
    return result


def evaluate_sentiment(texts: list[str], labels: list[str]) -> dict[str, Any]:
    """Measure the baseline against supplied labels without training on the test data."""
    allowed = {"positive", "neutral", "negative"}
    normalized_labels = [str(label).strip().casefold() for label in labels]
    if not texts or len(texts) != len(normalized_labels):
        raise ValueError("Labeled evaluation requires matching non-empty text and label columns.")
    invalid = sorted(set(normalized_labels) - allowed)
    if invalid:
        raise ValueError(f"Labels must be positive, neutral, or negative; found: {', '.join(invalid)}.")
    predictions = [sentiment_prediction(text)["sentiment"] for text in texts]
    order = ["positive", "neutral", "negative"]
    return {
        "examples": len(texts),
        "labels": order,
        "accuracy": round(float(accuracy_score(normalized_labels, predictions)), 4),
        "per_class": classification_report(
            normalized_labels, predictions, labels=order, output_dict=True, zero_division=0
        ),
        "confusion_matrix": confusion_matrix(normalized_labels, predictions, labels=order).tolist(),
        "model": "SocialPulse lexicon baseline",
        "note": "Metrics describe only the supplied labeled dataset and its label mapping.",
    }


def compare_brands(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(records)
    if frame.empty or "brand" not in frame:
        return []
    result = []
    for brand, group in frame[frame["brand"].astype(str).str.len() > 0].groupby("brand"):
        counts = group["sentiment"].value_counts().to_dict()
        result.append({
            "brand": str(brand),
            "mentions": int(len(group)),
            "positive": int(counts.get("positive", 0)),
            "neutral": int(counts.get("neutral", 0)),
            "negative": int(counts.get("negative", 0)),
        })
    return sorted(result, key=lambda item: item["mentions"], reverse=True)
