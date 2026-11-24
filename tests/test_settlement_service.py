import pytest

from app.business import DomainIssue
from app.settlement.service import execute, review


def approve(store, run, note="本期核对无误，签发"):
    return review(
        store, run["id"], dict(revision=run["revision"], status="APPROVED", note=note)
    )


def test_periods_increment_and_three_department_lists(settle_store, settle_q1):
    run = execute(settle_store, settle_q1)
    assert run["period"] == 1 and run["status"] == "PENDING"
    report = run["report"]
    assert [d["department"] for d in report["departments"]] == ["D1", "D2", "D3"]
    assert report["balance"]["balanced"] is True


def test_same_source_rerun_creates_no_new_settlement(settle_store, settle_q1):
    first = execute(settle_store, settle_q1)
    second = execute(settle_store, settle_q1)
    assert first == second
    assert len(settle_store.list()) == 1


def test_different_source_opens_next_period(settle_store, settle_q1, settle_q2):
    approve(settle_store, execute(settle_store, settle_q1))
    second = execute(settle_store, settle_q2)
    assert second["period"] == 2
    assert len(settle_store.list()) == 2


def test_approved_history_is_skipped_in_next_period(settle_store, settle_q1, settle_q2):
    approve(settle_store, execute(settle_store, settle_q1))
    report = execute(settle_store, settle_q2)["report"]
    by_dept = {d["department"]: d for d in report["departments"]}
    skipped = {(s["kind"], s["id"]) for d in report["departments"] for s in d["skipped"]}
    # 上一期已结算的对象与闭合链快照在增量期被跳过，不重复返还。
    assert ("snapshot", "S3") in skipped
    assert ("object", "o3") in skipped
    # 本期才退完的 S1 在 D1 结算一次。
    d1_items = [(i["kind"], i["id"]) for i in by_dept["D1"]["items"]]
    assert ("snapshot", "S1") in d1_items


def test_blocked_batch_is_not_persisted(settle_store, settle_q1, settle_dirty):
    approve(settle_store, execute(settle_store, settle_q1))
    before = len(settle_store.list())
    with pytest.raises(DomainIssue, match="SETTLEMENT_BLOCKED") as error:
        execute(settle_store, settle_dirty)
    assert error.value.details["reasons"]
    # 旧版清单保留，期次与历史都不被坏批次改写。
    assert len(settle_store.list()) == before


def test_approved_settlement_is_final(settle_store, settle_q1):
    run = approve(settle_store, execute(settle_store, settle_q1))
    with pytest.raises(DomainIssue, match="RUN_FINALIZED"):
        review(
            settle_store,
            run["id"],
            dict(revision=run["revision"], status="HELD", note="试图撤销已签发清单"),
        )


def test_review_optimistic_lock(settle_store, settle_q1):
    run = execute(settle_store, settle_q1)
    payload = dict(revision=0, status="HELD", note="等待补录来源")
    review(settle_store, run["id"], payload)
    with pytest.raises(DomainIssue, match="STALE_REVIEW"):
        review(settle_store, run["id"], payload)


def test_settled_history_only_includes_approved(settle_store, settle_q1):
    run = execute(settle_store, settle_q1)
    assert settle_store.settled_history() == {"objects": set(), "snapshots": set()}
    approve(settle_store, run)
    history = settle_store.settled_history()
    assert "S2" in history["snapshots"] and "S3" in history["snapshots"]
    assert "o6" in history["objects"]
