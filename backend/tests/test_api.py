import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_sentiment_endpoint(client):
    assert client.get("/health").json()["status"] == "ok"
    response = client.post("/predict/sentiment", json={"text": "great service"})
    assert response.status_code == 200
    assert response.json()["sentiment"] == "positive"


def test_first_run_demo_endpoint_returns_derived_synthetic_dashboard(client):
    response = client.get("/demo/dashboard")
    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["source"]["is_live"] is False
    assert dashboard["summary"]["total_posts"] == len(dashboard["records"])
    assert dashboard["summary"]["total_posts"] > 100
    assert any(trend["topic"] == "camera" for trend in dashboard["trends"]["trends"])


def test_dataset_upload_stores_aggregate_history_only(client):
    response = client.post(
        "/analyze/dataset",
        files={"file": ("sample.csv", b"text,date\nGreat product,2026-01-01\nBad delay,2026-01-08\n", "text/csv")},
        data={"text_column": "text", "timestamp_column": "date"},
    )
    assert response.status_code == 200
    assert response.json()["summary"]["total_posts"] == 2
    history = client.get("/analytics/history")
    assert history.status_code == 200
    assert "text" not in str(history.json())


def test_invalid_upload_and_forecast_validation(client):
    response = client.post(
        "/analyze/dataset",
        files={"file": ("dataset.txt", b"text\nhello", "text/plain")},
    )
    assert response.status_code == 400
    response = client.post("/forecast", json={
        "topic": "camera",
        "points": [{"date": "2026-01-01", "count": 2}],
        "horizon": 2,
    })
    assert response.status_code == 422


def test_evaluation_endpoint_reports_metrics_for_uploaded_labels(client):
    response = client.post(
        "/evaluate/sentiment",
        files={"file": ("labels.csv", b"post,label\ngreat service,positive\nbad delay,negative\n", "text/csv")},
        data={"text_column": "post", "label_column": "label"},
    )
    assert response.status_code == 200
    assert response.json()["examples"] == 2
    assert "confusion_matrix" in response.json()


def test_json_batch_endpoints_enforce_text_size_limits(client):
    topics = client.post("/analyze/topics", json={"texts": ["x" * 10_001]})
    trends = client.post("/analyze/trends", json={
        "records": [{"text": "x" * 10_001, "timestamp": "2026-01-01"}],
    })
    assert topics.status_code == 422
    assert trends.status_code == 422


def test_topic_route_returns_evidence_and_rejects_misaligned_sentiments(client):
    response = client.post("/analyze/topics", json={
        "texts": [
            "camera photo quality is excellent",
            "camera photos look great",
            "delivery order arrived late",
            "delivery service was delayed",
        ],
        "sentiments": ["positive", "positive", "negative", "negative"],
    })
    assert response.status_code == 200
    topic = response.json()["topics"][0]
    assert topic["mentions"] > 0
    assert topic["representative_posts"]
    assert topic["sentiment_distribution"]
    assert "quality_metric" in response.json()

    invalid = client.post("/analyze/topics", json={
        "texts": ["camera", "delivery"],
        "sentiments": ["positive"],
    })
    assert invalid.status_code == 422


def test_json_import_uses_imported_source_and_normalized_records(client):
    response = client.post(
        "/analyze/import",
        files={
            "file": (
                "posts.json",
                b'{"records":[{"text":"Great camera quality","timestamp":"2026-10-01","brand":"Aurora"}]}',
                "application/json",
            )
        },
        data={"timestamp_column": "timestamp", "brand_column": "brand"},
    )
    assert response.status_code == 200
    imported = response.json()
    assert imported["source"]["type"] == "imported"
    assert imported["source"]["name"] == "posts.json"
    assert imported["records"][0]["post_id"]
    assert imported["records"][0]["sentiment"] == "positive"


def test_import_route_rejects_malformed_json_and_unknown_extensions(client):
    malformed = client.post(
        "/analyze/import",
        files={"file": ("posts.json", b"{invalid", "application/json")},
    )
    assert malformed.status_code == 422
    unsupported = client.post(
        "/analyze/import",
        files={"file": ("posts.xml", b"<posts/>", "application/xml")},
    )
    assert unsupported.status_code == 400


def test_forecast_endpoint_returns_chronological_comparison(client):
    response = client.post("/forecast", json={
        "topic": "camera",
        "points": [
            {"date": f"2026-10-{day:02d}", "count": day % 6}
            for day in range(1, 31)
        ],
        "horizon": 3,
    })
    assert response.status_code == 200
    result = response.json()
    assert result["topic"] == "camera"
    assert len(result["forecast"]) == 3
    assert result["holdout_predictions"]
    assert set(result["evaluation"]["models"]) == {
        "last_value_baseline", "holt_damped_trend",
    }
    assert "training-only validation" in result["evaluation"]["split"]


def test_trend_endpoint_uses_configured_calendar_windows(client):
    response = client.post("/analyze/trends", json={
        "window_days": 14,
        "min_mentions": 1,
        "records": [
            {"text": "camera quality", "timestamp": "2026-10-01"},
            {"text": "camera quality", "timestamp": "2026-10-20"},
            {"text": "camera quality", "timestamp": "2026-10-21"},
        ],
    })
    assert response.status_code == 200
    assert response.json()["window_days"] == 14
    camera = next(item for item in response.json()["trends"] if item["topic"] == "camera")
    assert camera["window_days"] == 14
    assert camera["absolute_change"] == 1
