#!/usr/bin/env python3
"""Hadoop Streaming reducer for sorted word<TAB>count input."""

import sys

current = None
total = 0
for line in sys.stdin:
    key, separator, value = line.rstrip("\n").partition("\t")
    if not separator:
        continue
    try:
        count = int(value)
    except ValueError:
        continue
    if key != current:
        if current is not None:
            print(f"{current}\t{total}")
        current, total = key, count
    else:
        total += count
if current is not None:
    print(f"{current}\t{total}")

