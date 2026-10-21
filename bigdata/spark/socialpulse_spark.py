#!/usr/bin/env python3
"""PySpark word, hashtag, and lexicon sentiment aggregations for post CSV data."""

from __future__ import annotations

import argparse
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

POSITIVE_WORDS = (
    "amazing", "awesome", "best", "brilliant", "excellent", "fantastic",
    "good", "great", "happy", "love", "lovely", "perfect", "recommend",
    "useful", "wonderful",
)
NEGATIVE_WORDS = (
    "annoying", "awful", "bad", "broken", "delay", "disappointed",
    "disappointing", "hate", "issue", "late", "poor", "problem", "refund",
    "slow", "terrible", "unhappy", "worse", "worst",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_csv", help="Input CSV path visible to Spark")
    parser.add_argument("output_dir", help="New output directory; must not already exist")
    parser.add_argument("--text-column", default="text")
    args = parser.parse_args()

    spark = SparkSession.builder.appName("SocialPulseAnalytics").getOrCreate()
    try:
        posts = spark.read.option("header", True).option("escape", '"').csv(args.input_csv)
        if args.text_column not in posts.columns:
            raise ValueError(
                f"Text column {args.text_column!r} not found; available: {posts.columns}"
            )
        text = F.coalesce(F.col(args.text_column).cast("string"), F.lit(""))
        normalized = F.lower(
            F.regexp_replace(
                F.regexp_replace(
                    F.regexp_replace(text, r"https?://\S+|www\.\S+", " "),
                    r"(?<!\w)@\w+",
                    " ",
                ),
                "#",
                "",
            )
        )
        token_array = F.split(normalized, r"[^a-z0-9']+")
        cleaned_posts = posts.withColumn("normalized_text", normalized)
        word_frequency = (
            cleaned_posts.select(F.explode(token_array).alias("word"))
            .where((F.length("word") > 2) & (F.col("word") != ""))
            .groupBy("word")
            .count()
            .orderBy(F.desc("count"), "word")
        )
        hashtag_frequency = (
            posts.select(
                F.explode(
                    F.regexp_extract_all(
                        text, F.lit(r"#([A-Za-z0-9_]+)"), 1
                    )
                ).alias("hashtag")
            )
            .withColumn("hashtag", F.concat(F.lit("#"), F.lower("hashtag")))
            .groupBy("hashtag")
            .count()
            .orderBy(F.desc("count"), "hashtag")
        )
        positive_terms = F.array(*[F.lit(word) for word in POSITIVE_WORDS])
        negative_terms = F.array(*[F.lit(word) for word in NEGATIVE_WORDS])
        sentiment_counts = (
            cleaned_posts
            .withColumn("tokens", token_array)
            .withColumn("positive_matches", F.size(F.array_intersect("tokens", positive_terms)))
            .withColumn("negative_matches", F.size(F.array_intersect("tokens", negative_terms)))
            .withColumn(
                "sentiment",
                F.when(F.col("positive_matches") > F.col("negative_matches"), "positive")
                .when(F.col("negative_matches") > F.col("positive_matches"), "negative")
                .otherwise("neutral"),
            )
            .groupBy("sentiment")
            .count()
            .orderBy("sentiment")
        )

        output = Path(args.output_dir)
        word_frequency.write.mode("errorifexists").option("header", True).csv(
            str(output / "word_frequency")
        )
        hashtag_frequency.write.mode("errorifexists").option("header", True).csv(
            str(output / "hashtag_frequency")
        )
        sentiment_counts.write.mode("errorifexists").option("header", True).csv(
            str(output / "sentiment_aggregation")
        )
        cleaned_posts.write.mode("errorifexists").parquet(str(output / "normalized_posts"))
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
