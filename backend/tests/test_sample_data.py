from pathlib import Path
import subprocess
import sys

import pandas as pd

from backend.app.services.analytics import analyze_frame, load_csv_dataset


def test_bundled_synthetic_sample_runs_through_full_analysis():
    sample = Path(__file__).resolve().parents[2] / "data" / "sample" / "socialpulse_sample.csv"
    frame, stats = load_csv_dataset(
        sample.read_bytes(),
        text_column="text",
        timestamp_column="timestamp",
        platform_column="platform",
        brand_column="brand",
    )
    result = analyze_frame(frame, stats)
    assert result["summary"]["total_posts"] == 15
    assert stats["invalid_timestamps"] == 0
    assert result["summary"]["hashtags"] == []
    assert result["summary"]["sentiment_over_time"]
    assert result["records"][0]["brand"] == "Aurora"
    assert set(result["records"][0]["sentiment_scores"]) == {
        "positive", "neutral", "negative"
    }
    assert result["topics"]["topics"]
    assert result["analysis_mode"] == "local single-machine processing"
    assert pd.to_datetime([row["timestamp"] for row in result["records"]]).notna().all()


def test_sentiment_streaming_mapper_reducer_aggregate_valid_records():
    project_root = Path(__file__).resolve().parents[2]
    mapper = project_root / "bigdata" / "mapreduce" / "sentiment_mapper.py"
    reducer = project_root / "bigdata" / "mapreduce" / "sentiment_reducer.py"
    csv_input = (
        "post_id,text,timestamp,sentiment,topic\n"
        "1,good,2026-10-20T10:00:00Z,positive,camera\n"
        "2,great,2026-10-20T12:00:00Z,positive,camera\n"
        "3,bad,2026-10-20T14:00:00Z,negative,camera\n"
        "4,unknown,2026-10-21T10:00:00Z,invalid,camera\n"
    )
    mapped = subprocess.run(
        [sys.executable, str(mapper)], input=csv_input, capture_output=True, text=True, check=True
    )
    reduced = subprocess.run(
        [sys.executable, str(reducer)],
        input="".join(sorted(mapped.stdout.splitlines(keepends=True))),
        capture_output=True,
        text=True,
        check=True,
    )
    assert reduced.stdout.splitlines() == [
        "2026-10-20|camera|negative\t1",
        "2026-10-20|camera|positive\t2",
    ]


def test_word_and_hashtag_streaming_jobs_skip_headers_and_aggregate_posts():
    project_root = Path(__file__).resolve().parents[2]
    mapper_dir = project_root / "bigdata" / "mapreduce"
    records = (
        "post_id,text,timestamp\n"
        '1,"Great camera #Camera #launch",2026-10-20\n'
        '2,"Great quality #camera",2026-10-21\n'
    )
    outputs = {}
    for mapper_name in ("mapper.py", "hashtag_mapper.py"):
        mapper_result = subprocess.run(
            [sys.executable, str(mapper_dir / mapper_name)],
            input=records,
            capture_output=True,
            text=True,
            check=True,
        )
        reducer_result = subprocess.run(
            [sys.executable, str(mapper_dir / "reducer.py")],
            input="".join(sorted(mapper_result.stdout.splitlines(keepends=True))),
            capture_output=True,
            text=True,
            check=True,
        )
        outputs[mapper_name] = reducer_result.stdout.splitlines()

    assert "great\t2" in outputs["mapper.py"]
    assert outputs["hashtag_mapper.py"] == ["#camera\t2", "#launch\t1"]
