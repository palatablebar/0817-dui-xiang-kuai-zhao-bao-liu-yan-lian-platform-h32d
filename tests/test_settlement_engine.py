import pytest

from app.business import DomainIssue
from app.settlement.engine import adjudicate, build_model
from conftest import settle_data


def control():
    return ["C1", "control", "D1", "CTL", "CTL", "0", "0", "控制"]


def obj(record, dept, oid, size, leased):
    return [record, "object", dept, oid, "O", str(size), str(leased), "对象"]


def ref(record, dept, oid, sid):
    return [record, "ref", dept, oid, sid, "0", "0", "引用"]


def snap(record, dept, sid, size):
    return [record, "snapshot", dept, sid, sid, str(size), "0", "快照"]


def rows_of(data):
    from app.settlement.intake import inspect

    return inspect(data)["rows"]


def dept_map(decision):
    return {d["department"]: d for d in decision["departments"]}


def test_open_shared_chain_keeps_snapshot_in_retained():
    # S1 被 o1(D1,已退) 与 o2(D2,仍占用) 共享 -> 整条链未退完，留在共用保留。
    data = settle_data([
        control(),
        obj("O1", "D1", "o1", 100, 0),
        obj("O2", "D2", "o2", 50, 1),
        ref("R1", "D1", "o1", "S1"),
        ref("R2", "D2", "o2", "S1"),
        snap("S1r", "D1", "S1", 90),
    ])
    decision = adjudicate(rows_of(data))
    assert decision["totals"]["returned_bytes"] == 100  # 仅 o1 自身容量
    assert dept_map(decision)["D1"]["returned_bytes"] == 100
    retained = {(r["kind"], r["id"]): r for r in decision["retained"]}
    assert ("snapshot", "S1") in retained
    assert retained[("snapshot", "S1")]["reason"] == "SHARED_STILL_LEASED"
    assert retained[("snapshot", "S1")]["leased_members"] == ["o2"]
    assert ("object", "o2") in retained


def test_closed_chain_settles_snapshot_once_to_owner():
    # S1 被 D1 与 D2 对象共享，全部退完 -> 只在快照归属部门 D2 结算一次。
    data = settle_data([
        control(),
        obj("O1", "D1", "o1", 100, 0),
        obj("O2", "D2", "o2", 50, 0),
        ref("R1", "D1", "o1", "S1"),
        ref("R2", "D2", "o2", "S1"),
        snap("S1r", "D2", "S1", 90),
    ])
    decision = adjudicate(rows_of(data))
    d1, d2 = dept_map(decision)["D1"], dept_map(decision)["D2"]
    # 快照容量只出现一次，计入归属部门 D2；两部门各自对象容量仍分别返还。
    assert d1["returned_bytes"] == 100
    assert d2["returned_bytes"] == 50 + 90
    snapshot_items = [i for i in d2["items"] if i["kind"] == "snapshot"]
    assert len(snapshot_items) == 1 and snapshot_items[0]["reason"] == "CHAIN_CLOSED"
    assert decision["retained"] == []


def test_shared_snapshot_capacity_is_never_double_counted():
    # 退租方各持一条引用，但同一快照容量在整批返还中只能出现一次。
    data = settle_data([
        control(),
        obj("O1", "D1", "o1", 100, 0),
        obj("O2", "D2", "o2", 50, 0),
        obj("O3", "D3", "o3", 20, 0),
        ref("R1", "D1", "o1", "S1"),
        ref("R2", "D2", "o2", "S1"),
        ref("R3", "D3", "o3", "S1"),
        snap("S1r", "D1", "S1", 90),
    ])
    decision = adjudicate(rows_of(data))
    snapshot_bytes = sum(
        i["size_bytes"]
        for dept in decision["departments"]
        for i in dept["items"]
        if i["kind"] == "snapshot"
    )
    # 90 的快照容量恰好一次；对象容量 170 各自返还，合计 260。
    assert snapshot_bytes == 90
    assert decision["totals"]["returned_bytes"] == 100 + 50 + 20 + 90


def test_history_settled_identifiers_are_skipped():
    data = settle_data([
        control(),
        obj("O1", "D1", "o1", 100, 0),
        snap("S1r", "D1", "S1", 90),
        ref("R1", "D1", "o1", "S1"),
    ])
    history = {"objects": {"o1"}, "snapshots": {"S1"}}
    decision = adjudicate(rows_of(data), history=history)
    d1 = dept_map(decision)["D1"]
    assert d1["returned_bytes"] == 0 and d1["items"] == []
    assert {s["id"] for s in d1["skipped"]} == {"o1", "S1"}
    assert decision["totals"]["skipped"] == 2


def test_released_object_returns_own_capacity():
    data = settle_data([
        control(),
        obj("O1", "D3", "o1", 70, 0),
    ])
    decision = adjudicate(rows_of(data))
    d3 = dept_map(decision)["D3"]
    assert d3["returned_bytes"] == 70
    assert d3["items"][0]["reason"] == "OBJECT_RELEASED"


def test_all_three_departments_always_present_even_when_empty():
    data = settle_data([control(), obj("O1", "D1", "o1", 10, 0)])
    decision = adjudicate(rows_of(data))
    assert [d["department"] for d in decision["departments"]] == ["D1", "D2", "D3"]
    assert dept_map(decision)["D2"]["items"] == []


def test_dangling_snapshot_reference_blocks():
    data = settle_data([
        control(),
        obj("O1", "D1", "o1", 10, 0),
        ref("R1", "D1", "o1", "S404"),
    ])
    with pytest.raises(DomainIssue, match="SETTLEMENT_BLOCKED") as error:
        build_model(rows_of(data))
    assert "DANGLING_SNAPSHOT" in error.value.details["reasons"]


def test_ref_department_must_match_its_object():
    data = settle_data([
        control(),
        obj("O1", "D1", "o1", 10, 0),
        snap("S1r", "D2", "S1", 90),
        ref("R1", "D3", "o1", "S1"),  # 引用方部门与其对象 D1 不一致
    ])
    with pytest.raises(DomainIssue) as error:
        build_model(rows_of(data))
    assert "REF_DEPARTMENT_MISMATCH" in error.value.details["reasons"]


def test_orphan_snapshot_blocks():
    data = settle_data([
        control(),
        snap("S1r", "D1", "S1", 90),  # 没有任何 ref 挂接
    ])
    with pytest.raises(DomainIssue) as error:
        build_model(rows_of(data))
    assert "ORPHAN_SNAPSHOT" in error.value.details["reasons"]


def test_missing_control_row_blocks():
    data = settle_data([obj("O1", "D1", "o1", 10, 0)])
    with pytest.raises(DomainIssue) as error:
        build_model(rows_of(data))
    assert "CONTROL_COUNT" in error.value.details["reasons"]


def test_conflicting_object_definition_blocks():
    data = settle_data([
        control(),
        obj("O1", "D1", "o1", 10, 0),
        obj("O1b", "D1", "o1", 20, 0),  # 同对象不同容量
        snap("S1r", "D1", "S1", 90),
        ref("R1", "D1", "o1", "S1"),
    ])
    with pytest.raises(DomainIssue) as error:
        build_model(rows_of(data))
    assert "OBJECT_CONFLICT" in error.value.details["reasons"]
