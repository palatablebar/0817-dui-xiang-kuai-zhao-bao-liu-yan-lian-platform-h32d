"""退租结算 HTTP 接口。"""

from flask import Blueprint, Response, current_app, jsonify, request

from app.inputs import read_settlement_input
from app.settlement.render import artifact
from app.settlement.service import execute, review

settlement_api = Blueprint("settlement_api", __name__, url_prefix="/api/settlements")


@settlement_api.post("/preview")
def preview():
    """阶段预览：不落库，返回完整裁决报告（含阻断原因）。"""
    store = current_app.extensions["settlements"]
    # 预览也使用当前历史去重口径，但绝不写库。
    from app.settlement.pipeline import evaluate

    report = evaluate(
        read_settlement_input(), history=store.settled_history()
    )
    return jsonify(report)


@settlement_api.route("", methods=["GET", "POST"])
def settlements():
    store = current_app.extensions["settlements"]
    if request.method == "GET":
        return jsonify(items=store.list())
    return jsonify(execute(store, read_settlement_input()))


@settlement_api.route("/<run_id>", methods=["GET", "PATCH"])
def batch(run_id):
    store = current_app.extensions["settlements"]
    if request.method == "GET":
        return jsonify(store.load(run_id))
    return jsonify(review(store, run_id, request.get_json(silent=True)))


@settlement_api.get("/<run_id>/evidence")
def export(run_id):
    run = current_app.extensions["settlements"].load(run_id)
    return Response(
        artifact(run),
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="settlement-{run["id"][:12]}.json"',
            "Cache-Control": "no-store",
        },
    )
