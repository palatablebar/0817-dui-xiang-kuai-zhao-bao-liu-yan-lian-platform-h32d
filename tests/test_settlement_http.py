import io

from app.main import create_app


def test_preview_does_not_persist(client, settle_q1):
    resp = client.post("/api/settlements/preview", data={"file": (io.BytesIO(settle_q1), "q1.csv")})
    assert resp.status_code == 200
    payload = resp.json
    assert [d["department"] for d in payload["departments"]] == ["D1", "D2", "D3"]
    assert client.get("/api/settlements").json == {"items": []}


def test_preview_sample_and_execute_flow(client):
    preview = client.post("/api/settlements/preview", data={"sample": "q1"})
    assert preview.status_code == 200 and preview.json["balance"]["balanced"]
    run = client.post("/api/settlements", data={"sample": "q1"})
    assert run.status_code == 200 and run.json["period"] == 1
    assert client.get("/api/settlements").json["items"][0]["status"] == "PENDING"


def test_same_source_upload_matches_sample_run(client, settle_q1):
    uploaded = client.post(
        "/api/settlements", data={"file": (io.BytesIO(settle_q1), "q1.csv")}
    )
    sampled = client.post("/api/settlements", data={"sample": "q1"})
    assert uploaded.json["id"] == sampled.json["id"]


def test_blocked_batch_returns_422_with_reasons(client, settle_dirty):
    resp = client.post("/api/settlements", data={"sample": "dirty"})
    assert resp.status_code == 422
    body = resp.json
    assert body["code"] == "SETTLEMENT_BLOCKED"
    assert body["details"]["reasons"]
    # 阻断批次不落库，历史保持空。
    assert client.get("/api/settlements").json == {"items": []}


def test_review_and_evidence_end_to_end(client):
    run = client.post("/api/settlements", data={"sample": "q1"}).json
    patched = client.patch(
        f"/api/settlements/{run['id']}",
        json=dict(revision=0, status="APPROVED", note="季度返还清单签发"),
    )
    assert patched.status_code == 200 and patched.json["status"] == "APPROVED"
    evidence = client.get(f"/api/settlements/{run['id']}/evidence")
    assert evidence.status_code == 200
    assert "attachment" in evidence.headers["Content-Disposition"]
    packet = evidence.json
    assert packet["schema"] == "settlement-evidence/1"
    assert packet["review"]["note"] == "季度返还清单签发"
    assert [d["department"] for d in packet["departments"]] == ["D1", "D2", "D3"]


def test_settlement_not_found_is_404(client):
    assert client.get("/api/settlements/missing").status_code == 404


def test_settlement_sample_download(client, settle_q1):
    resp = client.get("/settlement/examples/q1")
    assert resp.status_code == 200 and resp.data == settle_q1
    assert client.get("/settlement/examples/nope").status_code == 404


def test_unknown_settlement_sample_is_404(client):
    resp = client.post("/api/settlements", data={"sample": "nope"})
    assert resp.status_code == 404 and resp.json["code"] == "SAMPLE_UNKNOWN"


def test_settlement_store_is_separate_from_review_runs(client, settle_q1):
    client.post("/api/settlements", data={"sample": "q1"})
    # 退租结算不污染保留演练台的批次表。
    assert client.get("/api/runs").json == {"items": []}
