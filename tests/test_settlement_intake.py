import pytest

from app.business import DomainIssue
from app.settlement.intake import inspect
from conftest import settle_data


def srow(record="S001", kind="object", dept="D1", oid="o1", sid="S1",
         size="10", leased="0", note="校核"):
    return [record, kind, dept, oid, sid, size, leased, note]


def test_bom_preserves_record_key():
    data = b"\xef\xbb\xbf" + settle_data([srow()])
    assert inspect(data)["rows"][0]["record"] == "S001"


def test_full_width_and_grouping_sizes_are_canonical():
    row = inspect(settle_data([srow(size="１,２３４")]))["rows"][0]
    assert row["size_bytes"] == 1234


def test_unknown_department_is_isolated():
    result = inspect(settle_data([srow(dept="D9")]))
    assert result["reasons"] == {"SETTLE_UNKNOWN_DEPARTMENT": 1}
    assert not result["rows"]


def test_bad_leased_state_is_isolated():
    result = inspect(settle_data([srow(leased="2")]))
    assert result["reasons"] == {"SETTLE_BAD_LEASED": 1}


def test_extra_column_is_isolated():
    values = srow() + ["意外分隔"]
    stream_data = settle_data([values])
    # settle_data 已按 8 列写表头，这里手工拼一列坏行
    result = inspect(stream_data)
    assert result["reasons"] == {"SETTLE_COLUMN_COUNT": 1}


def test_duplicate_replay_keeps_one_row():
    result = inspect(settle_data([srow(), srow()]))
    assert result["accepted"] == 1 and result["reasons"] == {"SETTLE_DUPLICATE_REPLAY": 1}


def test_duplicate_conflict_isolates_both():
    result = inspect(settle_data([srow(size="10"), srow(size="20")]))
    assert not result["rows"] and result["reasons"] == {"SETTLE_DUPLICATE_CONFLICT": 2}


def test_unknown_kind_is_isolated():
    assert inspect(settle_data([srow(kind="ghost")]))["reasons"] == {
        "SETTLE_UNKNOWN_KIND": 1
    }


@pytest.mark.parametrize(
    "payload,reason",
    [
        (b"", "FILE_EMPTY"),
        (b" \r\n", "FILE_BLANK"),
        (settle_data([]), "HEADER_ONLY"),
    ],
)
def test_empty_states_have_distinct_causes(payload, reason):
    with pytest.raises(DomainIssue, match=reason):
        inspect(payload)


def test_wrong_header_rejected():
    with pytest.raises(DomainIssue, match="HEADER_MISMATCH"):
        inspect(b"record,kind,department\nx,object,D1\n")


def test_sample_dirty_isolates_bad_department(settle_dirty):
    info = inspect(settle_dirty)
    assert info["rejected"] == 1
    assert info["reasons"] == {"SETTLE_UNKNOWN_DEPARTMENT": 1}
