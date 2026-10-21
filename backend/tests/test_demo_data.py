from backend.app.services.demo_data import build_demo_analysis


def test_demo_dashboard_has_derived_synthetic_records_and_trend_evidence():
    result = build_demo_analysis()

    assert result["source"]["is_live"] is False
    assert result["source"]["type"] == "synthetic"
    assert result["analysis_mode"].startswith("synthetic demo data")
    assert result["summary"]["total_posts"] == len(result["records"])
    assert result["summary"]["total_posts"] > 100
    assert len({post["post_id"] for post in result["records"]}) == len(result["records"])
    assert set(result["summary"]["sentiment_counts"]) <= {"positive", "neutral", "negative"}

    camera = next(trend for trend in result["trends"]["trends"] if trend["topic"] == "camera")
    assert camera["current_mentions"] > camera["previous_mentions"]
    assert camera["growth_percent"] == 200
    assert camera["representative_posts"]
    assert result["insights"]
    assert {brand["brand"] for brand in result["brand_comparison"]} == {
        "Aurora", "Northstar", "Streamly",
    }


def test_demo_source_status_does_not_claim_live_or_hadoop_connections():
    from backend.app.main import demo_sources

    sources = demo_sources()
    assert sources["scheduler_active"] is False
    assert sources["refresh_policy"] == "manual"
    assert all(not source["live"] for source in sources["sources"])
    assert all(
        not source["connection_verified"]
        for source in sources["sources"]
        if source["type"] != "bundled generated data"
    )
