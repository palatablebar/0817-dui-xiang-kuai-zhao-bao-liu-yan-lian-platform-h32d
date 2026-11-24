"""三方对账：源对象、快照引用与隔离行任一对不上即整批阻断。"""


def reconcile(intake, decision):
    """核对输入守恒与领域覆盖，返回对账结果与阻断原因。"""
    reasons = []
    accepted = intake["accepted"]
    observed = (
        decision["meta"]["model_objects"]
        + decision["meta"]["model_snapshots"]
        + decision["meta"]["model_refs"]
        + 1  # 唯一 control 行
    )
    accounted = (
        intake["accepted"]
        + intake["rejected"]
        + intake["blank"]
        + intake["repeated"]
    )

    # 输入行守恒：所有读取到的逻辑行都必须有归宿。
    if accounted != intake["input"]:
        reasons.append("ROW_COUNT_MISMATCH")
    # 采信行必须全部进入领域模型，无遗漏、无重复。
    if observed != accepted:
        reasons.append("ACCEPTED_NOT_MODELED")
    # 存在隔离坏行时整批不出。
    if intake["rejected"]:
        reasons.append("ISOLATED_ROWS_PRESENT")

    return dict(
        input=intake["input"],
        accepted=accepted,
        isolated=intake["rejected"],
        ignored=intake["blank"] + intake["repeated"],
        modeled=observed,
        accounted=accounted,
        balanced=not reasons,
        reasons=sorted(set(reasons)),
        isolation=intake["isolation"],
    )
