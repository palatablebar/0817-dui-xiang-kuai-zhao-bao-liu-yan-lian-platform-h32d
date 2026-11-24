"""季度退租结算领域：共享快照返还裁决。

输入是按部门归集的退租来源（源对象 object、快照引用 ref、快照 snapshot、
批次控制 control）。模块负责：

- 采信并隔离坏行（``settlement.intake``）；
- 展开共享链并裁决每条快照是可返还还是留在共用保留（``settlement.engine``）；
- 与历史已签发清单去重、对账并落库期次（``settlement.service`` / ``store``）。
"""

# 三个退租部门，清单固定按此顺序产出，空部门也保留。
DEPARTMENTS = ("D1", "D2", "D3")

# 退租来源行类型。
KINDS = ("object", "ref", "snapshot", "control")

# 退租来源 CSV 列顺序（独立于保留演练台的字段字典）。
COLUMNS = ("record", "kind", "department", "object_id", "snapshot", "size_bytes", "leased", "note")

HEADER = tuple(COLUMNS)

# 退租状态取值：leased=1 表示该源对象仍被未退对象占用（未退完）。
LEASED_STATES = ("0", "1")

# 退租结算工作台页面配置。
SETTLE_VIEW = {
    "name": "季度退租结算工作台",
    "actor": "数据湖值班工程师",
    "samples": [("q1", "Q1 季度样例"), ("q2", "Q2 增量样例"), ("dirty", "阻断样例")],
}
