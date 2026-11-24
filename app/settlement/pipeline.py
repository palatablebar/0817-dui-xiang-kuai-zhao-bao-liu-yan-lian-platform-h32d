"""退租结算流水线：采信 -> 共享链裁决 -> 三方对账。

任何一环失败都整批阻断（``SETTLEMENT_BLOCKED``），错误体携带阻断原因，
由服务层保证不落库、保留旧版已签发清单。
"""

from app.business import DomainIssue
from app.settlement.engine import adjudicate, build_model
from app.settlement.intake import inspect
from app.settlement.reconcile import reconcile


def evaluate(data, history=None):
    """纯计算：返回完整结算报告；阻断时抛 ``DomainIssue``。"""
    intake = inspect(data)
    rows = intake["rows"]

    # build_model 先做领域约束校验，失败即阻断，不产出任何部门清单。
    model = build_model(rows)
    decision = adjudicate(rows, history=history, model=model)
    checks = reconcile(intake, decision)
    if not checks["balanced"]:
        raise DomainIssue("SETTLEMENT_BLOCKED", details=dict(reasons=checks["reasons"]))

    return dict(
        intake={k: v for k, v in intake.items() if k != "rows"},
        departments=decision["departments"],
        retained=decision["retained"],
        control=decision["control"],
        meta=decision["meta"],
        totals=decision["totals"],
        balance=checks,
    )
