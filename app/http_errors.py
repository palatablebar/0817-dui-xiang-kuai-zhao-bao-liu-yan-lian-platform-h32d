from flask import jsonify

LABELS = {
    "FILE_TOO_LARGE": "文件超过 256 KiB",
    "FILE_EMPTY": "文件没有内容",
    "FILE_BLANK": "文件只有空白",
    "HEADER_ONLY": "文件只有标题行",
    "HEADER_MISMATCH": "列名与字段字典不一致",
    "ENCODING_INVALID": "请使用 UTF-8 CSV",
    "CSV_MALFORMED": "CSV 引号或行格式异常",
    "ROW_LIMIT": "文件超过 2000 行",
    "FILE_REQUIRED": "请选择 CSV 文件",
    "RUN_NOT_FOUND": "批次不存在",
    "SETTLEMENT_NOT_FOUND": "结算期次不存在",
    "REVIEW_FIELDS": "请填写 3 至 200 字复核意见",
    "STALE_REVIEW": "批次已更新，请刷新",
    "RUN_FINALIZED": "批次已签发",
    "UNRESOLVED_ISSUES": "存在待处理差异",
    "SAMPLE_UNKNOWN": "样例不存在",
    "STAGE_UNKNOWN": "处理阶段不存在",
    # 退租结算阻断原因
    "SETTLEMENT_BLOCKED": "退租结算整批阻断，请按阻断原因核对来源",
    "SETTLE_COLUMN_COUNT": "退租来源列数不匹配",
    "SETTLE_BAD_IDENTIFIER": "退租记录键非法",
    "SETTLE_BAD_OBJECT_ID": "源对象标识非法",
    "SETTLE_BAD_SNAPSHOT_ID": "快照标识非法",
    "SETTLE_UNKNOWN_KIND": "退租来源类型未知",
    "SETTLE_UNKNOWN_DEPARTMENT": "部门必须为 D1、D2、D3",
    "SETTLE_BAD_LEASED": "退租状态必须为 0 或 1",
    "SETTLE_NOTE_TOO_LONG": "说明列超过 200 字",
    "SETTLE_DUPLICATE_CONFLICT": "重复退租记录内容冲突",
    "SETTLE_DUPLICATE_REPLAY": "重复回放已忽略",
}

NOT_FOUND = {"RUN_NOT_FOUND", "SAMPLE_UNKNOWN", "STAGE_UNKNOWN", "SETTLEMENT_NOT_FOUND"}
CONFLICT = {"STALE_REVIEW", "RUN_FINALIZED", "UNRESOLVED_ISSUES"}


def response(error):
    code = error.code
    status = (
        404
        if code in NOT_FOUND
        else (
            409
            if code in CONFLICT
            else 413 if code == "FILE_TOO_LARGE" else 422
        )
    )
    payload = {"code": code, "message": LABELS.get(code, code)}
    details = getattr(error, "details", None)
    if details:
        payload["details"] = details
    return jsonify(payload), status
