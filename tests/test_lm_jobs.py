"""
Tests de lm_jobs.py (migrados desde jetson-ai-operator).

Solo se migran los tests autónomos del store. Los tests originales de routing
por OperatorRuntime y de endpoints HTTP dependían de módulos no migrados
(runtime, task_queue, telemetry_store) y quedan fuera de alcance.
"""

from loombit_operator.lm_jobs import LMJobStore


def _fake_executor(**kwargs):
    return {
        "choices": [
            {
                "message": {
                    "content": f'```json\n{{"ok": true, "role": "{kwargs["role"]}"}}\n```',
                },
            }
        ]
    }


def test_lm_job_store_runs_json_job_with_executor(tmp_path):
    store = LMJobStore(store_path=tmp_path / "lm_jobs.json")
    job = store.submit(
        role="coder",
        task_type="schema_review",
        expectation="json",
        messages=[{"role": "user", "content": "return json"}],
    )

    completed = store.run(job.id, _fake_executor)

    assert completed.status == "completed"
    assert completed.validation["valid"] is True
    assert completed.result["parsed_json"] == {"ok": True, "role": "coder"}


def test_lm_job_store_reports_invalid_json_without_crashing(tmp_path):
    store_path = tmp_path / "lm_jobs.json"
    store_path.write_text("{not-valid-json", encoding="utf-8")

    store = LMJobStore(store_path=store_path)

    assert store.snapshot()["count"] == 0
    assert "invalid" in store.snapshot()["load_error"]
