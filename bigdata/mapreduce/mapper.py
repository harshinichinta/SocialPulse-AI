#!/usr/bin/env python3
"""Hadoop Streaming mapper: emit normalized word<TAB>1 pairs from CSV or plain text."""

import csv
import re
import sys

WORD = re.compile(r"[A-Za-z][A-Za-z0-9']{1,}")

for line in sys.stdin:
    try:
        fields = next(csv.reader([line]))
        if fields and fields[0].strip().casefold() in {"post_id", "id"}:
            continue
        text = fields[1] if len(fields) > 1 else line
    except csv.Error:
        text = line
    for token in WORD.findall(text.lower()):
        print(f"{token}\t1")
