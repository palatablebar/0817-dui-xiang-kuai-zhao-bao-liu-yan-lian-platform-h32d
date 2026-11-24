# 字段与业务定义

输入编码 UTF-8，允许 BOM。首行必须匹配样例列顺序。记录键和业务组保留原始字符串。`kind` 允许 object, ref, snapshot, control。说明列 `note` 可以跨行，限制 200 字。

业务字段按 `object_id`、`snapshot`、`day`、`size_bytes`、`policy` 排列。数字接受非负整数、全角数字和完整千分位。空串、短横线、N/A、NULL 与未知为缺值。无关字段用 0 占位。

保全对象、活动快照引用及保留期内对象均留存。入库日小于等于当前日减保留期时到期。结果只生成回收候选和保留依据。

`incoming.csv` 包含四个业务组，第二组提供不同边界，第三组触发业务拒收，第四组需要核对。另含重复表头、冲突记录、重复回放与错误列数。`ready.csv` 含可以签发的两个组。

## 退租结算来源（settle_*.csv）

UTF-8、允许 BOM，首行列顺序固定为
`record,kind,department,object_id,snapshot,size_bytes,leased,note`。

- `record` 记录键保留前导零；`kind` 为 `object`、`ref`、`snapshot`、`control`。
- `department` 仅 `D1`、`D2`、`D3`，清单固定按此三部门产出，空部门也保留。
- `size_bytes` 接受非负整数、全角数字与完整千分位；`leased` 仅 `0/1`，`1` 表示仍被未退对象占用。
- `ref` 的部门须与其引用对象一致；快照归属由 `snapshot` 行部门决定，共享链可跨部门。
- `settle_q1.csv` 含未退完共享链（留保留）、已闭合跨部门链（只结算一次）；
  `settle_q2.csv` 为 Q1 签发后的增量，演示历史跳过与本期闭合；
  `settle_dirty.csv` 含非法部门与悬空快照引用，触发整批阻断。
