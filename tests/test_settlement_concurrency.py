from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from app.business import DomainIssue
from app.settlement.service import execute, review


def test_parallel_settlement_rerun_commits_single_period(settle_store, settle_q1):
    start = Barrier(4)

    def load():
        start.wait(3)
        return execute(settle_store, settle_q1)

    with ThreadPoolExecutor(max_workers=4) as threads:
        results = list(threads.map(lambda _: load(), range(4)))
    assert all(result == results[0] for result in results)
    assert len(settle_store.list()) == 1


def test_parallel_settlement_review_has_one_winner(settle_store, settle_q1):
    run = execute(settle_store, settle_q1)
    start = Barrier(2)

    def attempt(note):
        start.wait(3)
        try:
            return review(
                settle_store,
                run["id"],
                dict(revision=0, status="HELD", note=note),
            )["status"]
        except DomainIssue as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as threads:
        results = list(threads.map(attempt, ["来源待核对", "部门待确认"]))
    assert sorted(results) == ["HELD", "STALE_REVIEW"]
    assert settle_store.load(run["id"])["revision"] == 1
