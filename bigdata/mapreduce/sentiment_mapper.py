#!/usr/bin/env python3
"""Emit day|topic|sentiment keys from processed CSV rows for Hadoop Streaming."""

import csv
import sys

reader = csv.reader(sys.stdin)
for fields in reader:
    if not fields or fields[0].strip().casefold() == "post_id":
        continue
    if len(fields) < 5:
        continue
    post_id, text, timestamp, sentiment, topic = (field.strip() for field in fields[:5])
    date = timestamp[:10]
    if not date or sentiment.casefold() not in {"positive", "neutral", "negative"}:
        continue
    if not topic:
        topic = "unassigned"
    print(f"{date}|{topic.casefold()}|{sentiment.casefold()}\t1")

