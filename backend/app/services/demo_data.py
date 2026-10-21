"""Deterministic, explicitly synthetic records for the first-run demo experience."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from backend.app.services.analytics import analyze_frame, compare_brands, sentiment_prediction

TOPICS = {
    "camera": {
        "brand": "Aurora",
        "positive": [
            "Aurora camera photos look amazing and the picture quality is great",
            "Love the crisp camera detail on this Aurora phone",
        ],
        "negative": [
            "Aurora camera focus is slow and the image quality is disappointing",
            "The latest camera update has a broken zoom and blurry photos",
        ],
        "neutral": [
            "Testing the new Aurora camera settings this afternoon",
            "Aurora camera update includes a portrait mode option",
        ],
    },
    "delivery": {
        "brand": "Northstar",
        "positive": [
            "Northstar delivery arrived early and the tracking was useful",
            "Great delivery updates from the Northstar support team",
        ],
        "negative": [
            "Northstar delivery is late again and the tracking is broken",
            "The order delay was frustrating and customer support was slow",
        ],
        "neutral": [
            "Checking the Northstar delivery status for my order",
            "Northstar order tracking shows the package in transit",
        ],
    },
    "battery": {
        "brand": "Aurora",
        "positive": [
            "Aurora battery life is excellent and lasts all day",
            "Happy with the useful battery update on my Aurora phone",
        ],
        "negative": [
            "Aurora battery drains fast after the latest software update",
            "Battery life is disappointing and the phone gets warm",
        ],
        "neutral": [
            "Reviewing Aurora battery settings after the update",
            "The battery page now shows daily usage details",
        ],
    },
    "streaming": {
        "brand": "Streamly",
        "positive": [
            "Streamly playback is smooth and the new recommendations are great",
            "Love the clear video quality on Streamly this week",
        ],
        "negative": [
            "Streamly keeps buffering and playback quality is poor",
            "The app has a problem and streaming is slow tonight",
        ],
        "neutral": [
            "Trying the Streamly app on a different device",
            "Streamly added a new category to the home page",
        ],
    },
    "support": {
        "brand": "Northstar",
        "positive": [
            "Northstar support solved my issue quickly, thank you",
            "Helpful customer service and a great refund update",
        ],
        "negative": [
            "Northstar support has not resolved the issue and the wait is awful",
            "The refund process is slow and customer service was disappointing",
        ],
        "neutral": [
            "Contacted Northstar support about the order status",
            "Waiting for a response from customer service",
        ],
    },
}


def build_demo_analysis() -> dict[str, Any]:
    """Create a reproducible synthetic dataset with recent topic-volume variation."""
    today = datetime.now(timezone.utc).date()
    records: list[dict[str, Any]] = []
    sequence = 0
    for offset in range(30):
        day = today - timedelta(days=29 - offset)
        for topic_index, (topic, content) in enumerate(TOPICS.items()):
            baseline = 2 + (topic_index % 2)
            if topic == "camera" and offset >= 23:
                volume = baseline + 4
            elif topic == "support" and 16 <= offset <= 22:
                volume = baseline + 2
            else:
                volume = baseline
            for index in range(volume):
                sequence += 1
                sentiment = ("positive", "negative", "neutral")[(offset + index + topic_index) % 3]
                choices = content[sentiment]
                text = choices[(offset + index) % len(choices)]
                records.append({
                    "post_id": f"DEMO-{sequence:04d}",
                    "text": text,
                    "processed_text": text.casefold(),
                    "timestamp": pd.Timestamp(
                        datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
                        + timedelta(minutes=(topic_index * 97 + index * 31) % 1440)
                    ),
                    "platform": ("Community", "Microblog", "Forum")[(offset + topic_index) % 3],
                    "brand": content["brand"],
                    "sentiment": sentiment_prediction(text)["sentiment"],
                })

    frame = pd.DataFrame.from_records(records)
    summary = analyze_frame(
        frame,
        {
            "rows_received": len(frame),
            "rows_analyzed": len(frame),
            "empty_text_rows_removed": 0,
            "duplicate_text_rows_removed": 0,
            "invalid_timestamps": 0,
            "text_column": "text",
            "timestamp_column": "timestamp",
            "platform_column": "platform",
            "brand_column": "brand",
            "encoding": "generated synthetic demo",
            "platforms": sorted(frame["platform"].unique().tolist()),
        },
    )
    for record, source in zip(summary["records"], records):
        record["post_id"] = source["post_id"]
    summary["analysis_mode"] = "synthetic demo data; local single-machine processing"
    summary["source"] = {
        "name": "SocialPulse synthetic demo",
        "type": "synthetic",
        "status": "available",
        "is_live": False,
    }
    summary["insights"] = build_rule_based_insights(summary)
    summary["brand_comparison"] = compare_brands(summary["records"])
    summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    return summary


def build_rule_based_insights(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    insights = []
    for trend in analysis["trends"]["trends"]:
        if trend["current_mentions"] < 8:
            continue
        insights.append({
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
            "recommendation": "Review the representative posts and validate this signal against a broader data source.",
        })
    negative = analysis["summary"]["sentiment_counts"].get("negative", 0)
    total = analysis["summary"]["total_posts"]
    if total and negative / total >= 0.35:
        insights.append({
            "title": "Negative sentiment is a sizeable share of this demo sample",
            "topic": None,
            "evidence": f"{negative} of {total} posts ({negative / total:.1%}) were classified negative by the lexicon baseline.",
            "period": "All synthetic demo records",
            "mentions": negative,
            "previous_mentions": None,
            "growth_percent": None,
            "sentiment_distribution": analysis["summary"]["sentiment_counts"],
            "keywords": [],
            "representative_posts": [],
            "limitation": "Synthetic sample and lexicon labels; not real customer feedback.",
            "recommendation": "Use this page to explore evidence; do not infer a real-world brand issue from demo data.",
        })
    return insights

