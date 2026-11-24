# 对象快照保留演练台规则登记

- 规模：中型

## 功能模块

| 模块 | 动作 | 接口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 样例采信 | 预览并定位坏行 | `POST /api/stages/intake` | `app/intake/service.py` | `tests/test_intake.py` |
| M2 引用展开 | 检查领域约束 | `POST /api/stages/prepare` | `app/modules/prepare.py` | `tests/test_prepare.py` |
| M3 保留裁决 | 查看业务计算结果 | `POST /api/stages/calculate` | `app/modules/calculate.py` | `tests/test_calculate.py` |
| M4 回收核量 | 查看签收判定 | `POST /api/stages/policy` | `app/modules/policy.py` | `tests/test_policy.py` |
| M5 运行对账 | 对照输入、采信和隔离行 | `POST /api/stages/balance` | `app/modules/reconcile.py` | `tests/test_reconcile.py` |
| M6 批次复核 | 执行批次并签发或暂缓 | `POST /api/runs、PATCH /api/runs/<id>` | `app/review/service.py` | `tests/test_review.py` |
| M7 证据交付 | 下载复核清单 | `GET /api/runs/<id>/evidence` | `app/evidence/render.py` | `tests/test_evidence.py` |
| S1 退租采信 | 退租来源坏行隔离 | `POST /api/settlements/preview` | `app/settlement/intake.py` | `tests/test_settlement_intake.py` |
| S2 共享链裁决 | 未退完留保留、退完只结算一次 | `POST /api/settlements/preview` | `app/settlement/engine.py` | `tests/test_settlement_engine.py` |
| S3 期次结算 | 历史去重、同源幂等、签发冻结 | `POST /api/settlements` | `app/settlement/service.py` | `tests/test_settlement_service.py` |
| S4 三方对账 | 源对象/快照引用/隔离行核对阻断 | `POST /api/settlements/preview` | `app/settlement/reconcile.py` | `tests/test_settlement_http.py` |
| S5 结算证据 | 下载三部门返还清单 | `GET /api/settlements/<id>/evidence` | `app/settlement/render.py` | `tests/test_settlement_http.py` |

## 输入陷阱

| 编号 | 规则 | 处理 | 测试 |
|---|---|---|---|
| TRAP-02 | 去除 BOM | `app/intake/reader.py` | `tests/test_intake.py::test_bom_preserves_identifier` |
| TRAP-03 | 按逻辑记录读取引号内换行 | `app/intake/reader.py` | `tests/test_intake.py::test_quoted_newline_is_one_logical_record` |
| TRAP-04 | 重复表头计入忽略行 | `app/intake/service.py` | `tests/test_intake.py::test_repeated_header_is_counted` |
| TRAP-05 | 异常列数隔离 | `app/intake/schema.py` | `tests/test_intake.py::test_extra_column_is_isolated` |
| TRAP-06 | 归一化全角数字和千分位 | `app/intake/numeric.py` | `tests/test_intake.py::test_full_width_and_grouping_are_canonical` |
| TRAP-07 | 空值行隔离 | `app/intake/numeric.py` | `tests/test_intake.py::test_sentinel_keeps_row_out_of_total` |
| TRAP-08 | 记录键保留前导零 | `app/intake/schema.py` | `tests/test_intake.py::test_bom_preserves_identifier` |
| TRAP-14 | 冲突版本都进入隔离 | `app/intake/resolve.py` | `tests/test_intake.py::test_duplicate_conflict_removes_both_copies` |
| TRAP-16 | 引号未闭合时拒收文件 | `app/intake/reader.py` | `tests/test_intake.py::test_unclosed_quote_invalidates_source` |
| TRAP-18 | 区分空文件、全空白和仅表头 | `app/intake/reader.py` | `tests/test_intake.py::test_empty_states_have_distinct_causes` |
| TRAP-26 | 拒绝旧版本复核 | `app/review/store.py` | `tests/test_review.py::test_review_optimistic_lock` |

## 领域反例

保全对象、活动快照引用及保留期内对象均留存。入库日小于等于当前日减保留期时到期。结果只生成回收候选和保留依据。

逐组预期结论见 `tests/test_policy.py`，计算过程证据见 `tests/test_calculate.py`。

## 季度退租结算规则

退租来源列：`record,kind,department,object_id,snapshot,size_bytes,leased,note`。
`department` 仅允许 `D1/D2/D3`；`kind` 为 `object/ref/snapshot/control`；`leased=1`
表示源对象仍被未退对象占用。每批恰好一条 `control` 行。

- **共享链裁决**：快照被多个对象（可跨部门）引用时构成共享链。链上任一对象
  `leased=1`，该快照留在共用保留（`SHARED_STILL_LEASED`），不返还容量；整条链
  全部退完时只结算一次，容量计入 `snapshot` 行归属部门（`CHAIN_CLOSED`）。
- **源对象返还**：`leased=0` 的对象按自身部门返还 `size_bytes`；`leased=1` 留保留。
- **历史去重**：已签发清单中的对象与快照写入 `settled_identifiers`，后续期次重报
  时跳过（`HISTORY_SETTLED`），增量只进入下一期，已签发清单不被改写。
- **同源幂等**：同一来源字节指纹重跑返回同一期次，不新增清单；不同来源开启下一
  期次（期次号取最大期次 + 1）。
- **整批阻断**：源对象、快照引用、隔离行任一对不上（悬空引用、孤儿快照、控制行
  数量不符、部门不一致、冲突定义、行守恒失败或存在隔离行）都抛 `SETTLEMENT_BLOCKED`，
  携带 `details.reasons`，不写库、保留旧版清单。

裁决用例见 `tests/test_settlement_engine.py`，期次与历史去重见
`tests/test_settlement_service.py`，阻断与 HTTP 见 `tests/test_settlement_http.py`。
