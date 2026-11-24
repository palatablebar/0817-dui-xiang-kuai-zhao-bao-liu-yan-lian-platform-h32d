# 对象快照保留演练台

数据湖值班工程师可在工作台上传来源 CSV，对照规则判断差异，签发合格批次或记录暂缓意见。

基于活动快照、保留期和合法保全计算可回收对象。

## 启动

```sh
docker compose up --build -d --wait
```

打开 <http://localhost:18311>。页面预览带异常样例。选中阶段查看计算证据，选择可签发样例并执行批次，然后提交复核意见。

## 核验

```sh
docker compose exec -T app pytest -q
```

## 季度退租结算

工作台在 <http://localhost:18311/settlement> 提供三个部门的季度返还清单：共享快照按
共享链是否全部退租裁决——未退完留在共用保留，整条链退完只结算一次；已签发清单不被
后续退租改写，历史已结算标识在增量期自动跳过；同来源重跑不新增期次；源对象、快照
引用或隔离行核对失败时整批阻断、保留旧版并标出原因。详见
[退租结算规则](docs/DEPTH.md#季度退租结算规则) 与 [接口](docs/HTTP.md)。

[输入字段](docs/DATA-DICTIONARY.md) · [阶段接口](docs/HTTP.md) · [操作步骤](docs/OPERATIONS.md) · [规则与测试](docs/DEPTH.md)
