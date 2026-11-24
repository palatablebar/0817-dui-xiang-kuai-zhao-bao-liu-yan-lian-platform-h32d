"""退租来源单行的字段校验。"""

import re

from app.business import DomainIssue
from app.intake.numeric import quantity
from app.settlement import DEPARTMENTS, HEADER, KINDS, LEASED_STATES

_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,35}")


def _identifier(value, reason):
    text = value.strip()
    if not _IDENTIFIER.fullmatch(text):
        raise DomainIssue(reason)
    return text


def record(values):
    """把一行原始 CSV 值归一化为退租来源记录，坏行抛 ``DomainIssue``。"""
    if len(values) != len(HEADER):
        raise DomainIssue("SETTLE_COLUMN_COUNT")
    row = dict(zip(HEADER, values))
    row["record"] = _identifier(row["record"], "SETTLE_BAD_IDENTIFIER")
    if row["kind"] not in KINDS:
        raise DomainIssue("SETTLE_UNKNOWN_KIND")
    department = row["department"].strip()
    if department not in DEPARTMENTS:
        raise DomainIssue("SETTLE_UNKNOWN_DEPARTMENT")
    row["department"] = department
    row["object_id"] = _identifier(row["object_id"], "SETTLE_BAD_OBJECT_ID")
    row["snapshot"] = _identifier(row["snapshot"], "SETTLE_BAD_SNAPSHOT_ID")
    row["size_bytes"] = quantity(row["size_bytes"])
    leased = row["leased"].strip()
    if leased not in LEASED_STATES:
        raise DomainIssue("SETTLE_BAD_LEASED")
    row["leased"] = int(leased)
    if len(row["note"]) > 200:
        raise DomainIssue("SETTLE_NOTE_TOO_LONG")
    return row
