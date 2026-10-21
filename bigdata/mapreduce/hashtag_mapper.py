#!/usr/bin/env python3
"""Hadoop Streaming mapper for hashtag frequency in a post_id,text CSV."""

import csv
import re
import sys

HASHTAG = re.compile(r"(?<!\w)#([A-Za-z0-9_]+)")

for line in sys.stdin:
    try:
        fields = next(csv.reader([line]))
        if fields and fields[0].strip().casefold() in {"post_id", "id"}:
            continue
        text = fields[1] if len(fields) > 1 else line
    except csv.Error:
        text = line
    for tag in HASHTAG.findall(text):
        print(f"#{tag.casefold()}\t1")
