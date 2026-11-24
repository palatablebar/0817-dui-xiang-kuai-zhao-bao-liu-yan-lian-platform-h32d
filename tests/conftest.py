import csv
import io
from pathlib import Path

import pytest

from app.intake.schema import HEADER
from app.main import create_app
from app.review.store import Store
from app.settlement.schema import HEADER as SETTLE_HEADER
from app.settlement.store import SettlementStore

ROOT = Path(__file__).resolve().parents[1]


def csv_data(records):
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows([HEADER, *records])
    return stream.getvalue().encode()


def settle_data(rows):
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows([SETTLE_HEADER, *rows])
    return stream.getvalue().encode()


@pytest.fixture
def dirty():
    return (ROOT / "sample_data" / "incoming.csv").read_bytes()


@pytest.fixture
def clean():
    return (ROOT / "sample_data" / "ready.csv").read_bytes()


@pytest.fixture
def settle_q1():
    return (ROOT / "sample_data" / "settle_q1.csv").read_bytes()


@pytest.fixture
def settle_q2():
    return (ROOT / "sample_data" / "settle_q2.csv").read_bytes()


@pytest.fixture
def settle_dirty():
    return (ROOT / "sample_data" / "settle_dirty.csv").read_bytes()


@pytest.fixture
def client(tmp_path):
    return create_app(tmp_path / "runs.db").test_client()


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "runs.db")


@pytest.fixture
def settle_store(tmp_path):
    return SettlementStore(tmp_path / "settlements.db")
