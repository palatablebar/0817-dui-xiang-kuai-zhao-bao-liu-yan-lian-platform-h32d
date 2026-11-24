"""共享链裁决：决定每条快照返还还是留在共用保留。

裁决原则（见需求）：

- 退租方希望按各自引用立即计入，但同一快照仍被未退对象（``leased=1``）引用时，
  不能重复返还，先留在共用保留；
- 整条共享链全部退完（所有引用对象 ``leased=0``）时，该快照只结算一次，
  计入快照归属部门的返还清单；
- 已在历史已签发清单出现的源对象/快照不再计入（增量只进入下一期）。
"""

from app.business import DomainIssue
from app.settlement import DEPARTMENTS


def _blank_departments():
    return {
        dept: dict(department=dept, returned_bytes=0, items=[], skipped=[])
        for dept in DEPARTMENTS
    }


def _block(reasons):
    raise DomainIssue("SETTLEMENT_BLOCKED", details=dict(reasons=sorted(set(reasons))))


def build_model(rows):
    """把采信行展开为对象、快照、引用与控制行，并做领域约束校验。"""
    reasons = []
    objects, snapshots, refs, controls = {}, {}, [], []
    object_dept = {}
    snapshot_dept = {}

    for row in rows:
        kind = row["kind"]
        dept = row["department"]
        if kind == "control":
            controls.append(row)
            continue
        if kind == "object":
            oid = row["object_id"]
            if oid in objects and (
                objects[oid]["size_bytes"] != row["size_bytes"]
                or object_dept[oid] != dept
                or objects[oid]["leased"] != row["leased"]
            ):
                reasons.append("OBJECT_CONFLICT")
            else:
                objects[oid] = row
                object_dept[oid] = dept
        elif kind == "snapshot":
            sid = row["snapshot"]
            if sid in snapshots and (
                snapshots[sid]["size_bytes"] != row["size_bytes"]
                or snapshot_dept[sid] != dept
            ):
                reasons.append("SNAPSHOT_CONFLICT")
            else:
                snapshots[sid] = row
                snapshot_dept[sid] = dept
        else:  # ref
            refs.append(row)

    if len(controls) != 1:
        reasons.append("CONTROL_COUNT")
    if reasons:
        _block(reasons)

    # 引用完整性与部门一致性。
    # 共享快照天然跨部门：ref 的部门只与其引用对象（引用方）一致，
    # 快照归属由 snapshot 行自身的部门决定，不要求 ref 与快照同部门。
    for ref in refs:
        if ref["object_id"] not in objects:
            reasons.append("DANGLING_OBJECT")
        if ref["snapshot"] not in snapshots:
            reasons.append("DANGLING_SNAPSHOT")
        if ref["object_id"] in objects and object_dept[ref["object_id"]] != ref["department"]:
            reasons.append("REF_DEPARTMENT_MISMATCH")
    if reasons:
        _block(reasons)

    # 快照必须至少被一条引用挂接，否则共享链无法核对。
    referenced = {ref["snapshot"] for ref in refs}
    if any(sid not in referenced for sid in snapshots):
        _block(reasons + ["ORPHAN_SNAPSHOT"])

    return dict(
        objects=objects,
        snapshots=snapshots,
        refs=refs,
        control=controls[0],
        object_dept=object_dept,
        snapshot_dept=snapshot_dept,
    )


def _sharing_chains(model):
    """snapshot_id -> 该链上的引用对象集合（去重）。"""
    chains = {sid: set() for sid in model["snapshots"]}
    for ref in model["refs"]:
        chains[ref["snapshot"]].add(ref["object_id"])
    return chains


def adjudicate(rows, history=None, model=None):
    """对一批退租来源裁决，返回三部门返还清单与共用保留。

    ``history`` 为历史已签发清单中已结算的标识，形如
    ``{"objects": {oid,...}, "snapshots": {sid,...}}``。``model`` 可传入已
    构建并校验过的领域模型以避免重复展开。任何领域校验失败都抛
    ``SETTLEMENT_BLOCKED`` 并携带阻断原因。
    """
    history = history or {"objects": set(), "snapshots": set()}
    if model is None:
        model = build_model(rows)
    departments = _blank_departments()
    retained = []
    chains = _sharing_chains(model)

    # 源对象：退完（leased=0）的对象按归属部门返还自身容量。
    for oid, row in sorted(model["objects"].items()):
        dept = model["object_dept"][oid]
        if row["leased"] == 1:
            retained.append(
                dict(kind="object", id=oid, department=dept,
                     size_bytes=row["size_bytes"], reason="STILL_LEASED")
            )
            continue
        if oid in history["objects"]:
            departments[dept]["skipped"].append(
                dict(kind="object", id=oid, reason="HISTORY_SETTLED")
            )
            continue
        departments[dept]["items"].append(
            dict(kind="object", id=oid, size_bytes=row["size_bytes"],
                 reason="OBJECT_RELEASED")
        )
        departments[dept]["returned_bytes"] += row["size_bytes"]

    # 快照：按共享链是否全部退完裁决，整条链退完只结算一次。
    for sid, srow in sorted(model["snapshots"].items()):
        dept = model["snapshot_dept"][sid]
        chain = sorted(chains[sid])
        leased_members = sorted(
            oid for oid in chain if model["objects"][oid]["leased"] == 1
        )
        if leased_members:
            retained.append(
                dict(kind="snapshot", id=sid, department=dept,
                     size_bytes=srow["size_bytes"], reason="SHARED_STILL_LEASED",
                     chain=chain, leased_members=leased_members)
            )
            continue
        if sid in history["snapshots"]:
            departments[dept]["skipped"].append(
                dict(kind="snapshot", id=sid, reason="HISTORY_SETTLED")
            )
            continue
        departments[dept]["items"].append(
            dict(kind="snapshot", id=sid, size_bytes=srow["size_bytes"],
                 reason="CHAIN_CLOSED", chain=chain)
        )
        departments[dept]["returned_bytes"] += srow["size_bytes"]

    return dict(
        departments=[departments[d] for d in DEPARTMENTS],
        retained=retained,
        control=dict(
            record=model["control"]["record"],
            department=model["control"]["department"],
            note=model["control"]["note"],
        ),
        meta=dict(
            model_objects=len(model["objects"]),
            model_snapshots=len(model["snapshots"]),
            model_refs=len(model["refs"]),
        ),
        totals=dict(
            returned_bytes=sum(d["returned_bytes"] for d in departments.values()),
            returned_items=sum(len(d["items"]) for d in departments.values()),
            retained=len(retained),
            skipped=sum(len(d["skipped"]) for d in departments.values()),
        ),
    )
