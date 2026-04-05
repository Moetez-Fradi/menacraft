from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_ingest_to_report_flow_text_only():
    payload = {
        "session_id": "integration-case-1",
        "text": "",
        "content_type": "text",
        "metadata": {"platform": "test"},
    }

    analyze = client.post("/v1/analyze", json=payload)
    assert analyze.status_code == 200
    body = analyze.json()
    assert "case_id" in body

    case_id = body["case_id"]
    report = client.get(f"/v1/cases/{case_id}/report")
    assert report.status_code == 200
    rep = report.json()
    assert rep["case_id"] == case_id
    assert "scores" in rep
    assert "evidence" in rep
