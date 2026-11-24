import os

from flask import Flask, jsonify, render_template, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge

from app.api import api
from app.business import DomainIssue
from app.config import MAX_FILE, ROOT
from app.http_errors import response
from app.review.store import Store
from app.settlement.http import settlement_api
from app.settlement.store import SettlementStore
from app.spec import PROJECT


def create_app(database=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_FILE + 16 * 1024
    app.extensions["runs"] = Store(
        database
        or os.getenv("WORKBENCH_DB", str(ROOT / "instance" / "workbench.sqlite3"))
    )
    app.extensions["settlements"] = SettlementStore(
        database
        or os.getenv("SETTLEMENT_DB", str(ROOT / "instance" / "settlements.sqlite3"))
    )
    app.register_error_handler(DomainIssue, response)
    app.register_error_handler(
        RequestEntityTooLarge, lambda _: response(DomainIssue("FILE_TOO_LARGE"))
    )
    app.register_blueprint(api)
    app.register_blueprint(settlement_api)

    @app.get("/")
    def home():
        return render_template("workbench.html", p=PROJECT)

    @app.get("/settlement")
    def settlement():
        from app.settlement import SETTLE_VIEW

        return render_template("settlement.html", p=SETTLE_VIEW)

    @app.get("/healthz")
    def health():
        return jsonify(status="ok")

    @app.get("/examples/<profile>")
    def example(profile):
        from app.inputs import SAMPLES

        if profile not in SAMPLES:
            raise DomainIssue("SAMPLE_UNKNOWN")
        return send_from_directory(
            ROOT / "sample_data", SAMPLES[profile], as_attachment=True
        )

    @app.get("/settlement/examples/<profile>")
    def settlement_example(profile):
        from app.inputs import SETTLEMENT_SAMPLES

        if profile not in SETTLEMENT_SAMPLES:
            raise DomainIssue("SAMPLE_UNKNOWN")
        return send_from_directory(
            ROOT / "sample_data", SETTLEMENT_SAMPLES[profile], as_attachment=True
        )

    return app


app = create_app()
