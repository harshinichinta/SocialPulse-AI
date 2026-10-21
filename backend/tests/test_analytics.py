import pandas as pd
import pytest

from backend.app.services.analytics import (
    detect_trends,
    discover_topics,
    forecast_series,
    load_csv_dataset,
    preprocess_text,
    sentiment_prediction,
)


def test_text_preprocessing_removes_url_and_mention_and_keeps_hashtag_word():
    assert preprocess_text("Hi @person #Great https://example.test") == "hi great"


def test_sentiment_baseline_returns_documented_schema():
    result = sentiment_prediction("This is an amazing and useful product")
    assert result["sentiment"] == "positive"
    assert set(result["class_scores"]) == {"positive", "neutral", "negative"}
    assert result["class_scores"]["positive"] > result["class_scores"]["neutral"]
    assert result["model"]["type"] == "rule-based baseline"


def test_dataset_validation_removes_empty_and_duplicate_text():
    csv = b"text,created_at\nGreat product,2026-01-01\n,2026-01-02\nGreat product,2026-01-03\n"
    frame, stats = load_csv_dataset(csv, timestamp_column="created_at")
    assert len(frame) == 1
    assert stats["empty_text_rows_removed"] == 1
    assert stats["duplicate_text_rows_removed"] == 1


def test_dataset_rejects_missing_text_column_and_bad_csv():
    with pytest.raises(ValueError, match="text column"):
        load_csv_dataset(b"date\n2026-01-01\n", text_column="text")
    with pytest.raises(ValueError, match="no data rows"):
        load_csv_dataset(b"\xff")
    with pytest.raises(ValueError, match="characters"):
        load_csv_dataset(("text\n" + "x" * 10_001).encode())


def test_dataset_falls_back_to_legacy_csv_encoding():
    frame, stats = load_csv_dataset("text\ncaf\xe9".encode("cp1252"))
    assert frame.iloc[0]["text"] == "café"
    assert stats["encoding"] == "cp1252"


def test_topics_handle_small_and_varied_datasets():
    assert discover_topics(["Great"]).get("topics")
    result = discover_topics([
        "camera photo quality excellent", "camera photos are great",
        "delivery order arrived late", "delivery was delayed",
    ])
    assert result["topics"]
    assert "representative_posts" in result["topics"][0]
    assert "sentiment_distribution" in result["topics"][0]
    assert "coherence" in result["topics"][0]
    assert "inspect representative posts" in result["message"]


def test_trend_growth_has_guard_for_small_previous_period():
    records = [
        {"text": "camera quality", "timestamp": "2026-10-01", "sentiment": "neutral"},
        {"text": "camera quality", "timestamp": "2026-10-08", "sentiment": "positive"},
        {"text": "camera quality", "timestamp": "2026-10-09", "sentiment": "positive"},
    ]
    result = detect_trends(records, window_days=7, min_mentions=2)
    camera = next(trend for trend in result["trends"] if trend["topic"] == "camera")
    assert camera["growth_percent"] is None
    assert "withheld" in camera["reason"]
    assert camera["representative_posts"]
    assert camera["keywords"]
    assert camera["absolute_change"] == 1
    assert camera["rank_score"] > 0


def test_trend_zero_baseline_has_guarded_growth_and_exposes_scoring():
    records = [
        {"text": "camera update", "timestamp": "2026-10-01", "sentiment": "neutral"},
        {"text": "camera update", "timestamp": "2026-10-10", "sentiment": "positive"},
        {"text": "camera update", "timestamp": "2026-10-15", "sentiment": "positive"},
    ]
    result = detect_trends(records, window_days=7, min_mentions=2)
    camera = next(trend for trend in result["trends"] if trend["topic"] == "camera")
    assert camera["previous_mentions"] == 0
    assert camera["current_mentions"] == 2
    assert camera["absolute_change"] == 2
    assert camera["growth_percent"] is None
    assert result["score_method"] == camera["score_method"]


def test_trend_detector_does_not_flag_flat_popular_topics_as_emerging():
    records = [
        {"text": "delivery service", "timestamp": "2026-10-01", "sentiment": "neutral"},
        {"text": "delivery service", "timestamp": "2026-10-02", "sentiment": "neutral"},
        {"text": "delivery service", "timestamp": "2026-10-08", "sentiment": "neutral"},
        {"text": "delivery service", "timestamp": "2026-10-09", "sentiment": "neutral"},
    ]
    result = detect_trends(records, window_days=7, min_mentions=2)
    assert result["trends"] == []


def test_forecast_requires_enough_periods_and_returns_holdout_metrics():
    with pytest.raises(ValueError, match="14 consecutive daily periods"):
        forecast_series([{"date": "2026-01-01", "count": 2}], 2)
    result = forecast_series([
        {"date": f"2026-01-{day:02d}", "count": day} for day in range(1, 31)
    ], 2)
    assert len(result["forecast"]) == 2
    assert result["evaluation"]["mae"] >= 0
    assert set(result["evaluation"]["models"]) == {
        "last_value_baseline", "holt_damped_trend",
    }
    assert result["holdout_predictions"]
    assert result["forecast"][0]["lower_bound"] is None


def test_labeled_evaluation_uses_supplied_ground_truth():
    from backend.app.services.analytics import evaluate_sentiment

    result = evaluate_sentiment(["great service", "terrible delay"], ["positive", "negative"])
    assert result["examples"] == 2
    assert result["accuracy"] == 1
    assert result["confusion_matrix"] == [[1, 0, 0], [0, 0, 0], [0, 0, 1]]
    with pytest.raises(ValueError, match="Labels must"):
        evaluate_sentiment(["text"], ["mixed"])
