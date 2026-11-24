"""退租来源的重复回放与冲突版本隔离。"""

from collections import defaultdict


def partition(candidates):
    """同 record 完全一致视为回放保留一份；内容冲突则两份都隔离。"""
    by_key = defaultdict(list)
    for line, row in candidates:
        by_key[row["record"]].append((line, row))
    accepted, rejected = [], []
    for key, entries in by_key.items():
        first = entries[0][1]
        if any(row != first for _, row in entries):
            rejected.extend(
                {
                    "line": line,
                    "record": key,
                    "case": row["department"],
                    "reason": "SETTLE_DUPLICATE_CONFLICT",
                }
                for line, row in entries
            )
            continue
        accepted.append(first)
        rejected.extend(
            {
                "line": line,
                "record": key,
                "case": row["department"],
                "reason": "SETTLE_DUPLICATE_REPLAY",
            }
            for line, row in entries[1:]
        )
    return accepted, rejected
