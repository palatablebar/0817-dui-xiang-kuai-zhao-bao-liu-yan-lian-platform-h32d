from flask import request

from app.business import DomainIssue
from app.config import MAX_FILE, ROOT

SAMPLES = {"dirty": "incoming.csv", "clean": "ready.csv"}
SETTLEMENT_SAMPLES = {
    "q1": "settle_q1.csv",
    "q2": "settle_q2.csv",
    "dirty": "settle_dirty.csv",
}


def read_input():
    sample = request.form.get("sample")
    if sample is not None:
        if sample not in SAMPLES:
            raise DomainIssue("SAMPLE_UNKNOWN")
        return (ROOT / "sample_data" / SAMPLES[sample]).read_bytes()
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        raise DomainIssue("FILE_REQUIRED")
    value = uploaded.stream.read(MAX_FILE + 1)
    if len(value) > MAX_FILE:
        raise DomainIssue("FILE_TOO_LARGE")
    return value


def read_settlement_input():
    sample = request.form.get("sample")
    if sample is not None:
        if sample not in SETTLEMENT_SAMPLES:
            raise DomainIssue("SAMPLE_UNKNOWN")
        return (ROOT / "sample_data" / SETTLEMENT_SAMPLES[sample]).read_bytes()
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        raise DomainIssue("FILE_REQUIRED")
    value = uploaded.stream.read(MAX_FILE + 1)
    if len(value) > MAX_FILE:
        raise DomainIssue("FILE_TOO_LARGE")
    return value
