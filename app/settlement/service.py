"""退租结算服务：期次执行、同源去重与签发复核。"""

from datetime import datetime, timezone
from hashlib import sha256
from time import monotonic

from app.business import DomainIssue
from app.config import SETTLEMENT_RULE_VERSION
from app.settlement.pipeline import evaluate


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def execute(store, data):
    """执行一期结算。

    - 同一来源（字节指纹 + 规则版本）重跑直接返回既有清单，不新增期次；
    - 阻断批次在 ``evaluate`` 内抛错，不写库，旧版清单原样保留；
    - 历史只统计已签发清单中已结算的标识，增量只进入下一期。
    """
    start = monotonic()
    fingerprint = sha256(data).hexdigest()
    run_id = sha256(
        f"{SETTLEMENT_RULE_VERSION}:settlement:{fingerprint}".encode()
    ).hexdigest()
    try:
        return store.load(run_id)
    except DomainIssue as error:
        if error.code != "SETTLEMENT_NOT_FOUND":
            raise

    history = store.settled_history()
    report = evaluate(data, history=history)
    report["period"] = store.next_period()
    report["manifest"] = dict(
        sha256=fingerprint,
        version=SETTLEMENT_RULE_VERSION,
        created=now(),
        duration_ms=round((monotonic() - start) * 1000, 3),
        bytes=len(data),
        run_id=run_id,
        kind="settlement",
    )
    return store.register(run_id, report)


def review(store, run_id, values):
    """签发/暂缓一期清单，带乐观锁；已签发清单不可改写。"""
    if not isinstance(values, dict):
        raise DomainIssue("REVIEW_FIELDS")
    revision, status, note = (values.get(key) for key in ("revision", "status", "note"))
    if (
        type(revision) is not int
        or revision < 0
        or status not in ("APPROVED", "HELD")
        or not isinstance(note, str)
        or not (3 <= len(note.strip()) <= 200)
    ):
        raise DomainIssue("REVIEW_FIELDS")
    current = store.load(run_id)
    if revision != current["revision"]:
        raise DomainIssue("STALE_REVIEW")
    if current["status"] == "APPROVED":
        raise DomainIssue("RUN_FINALIZED")
    if status == "APPROVED" and not current["report"]["balance"]["balanced"]:
        raise DomainIssue("UNRESOLVED_ISSUES")
    return store.revise(run_id, revision, status, note.strip(), now())
