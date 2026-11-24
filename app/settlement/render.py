"""退租结算证据包：冻结期次清单、对账与复核信息。"""

import json


def artifact(run):
    packet = {
        "schema": "settlement-evidence/1",
        "manifest": run["report"]["manifest"],
        "period": run["report"]["period"],
        "balance": run["report"]["balance"],
        "departments": run["report"]["departments"],
        "retained": run["report"]["retained"],
        "totals": run["report"]["totals"],
        "control": run["report"]["control"],
        "intake": run["report"]["intake"],
        "review": {
            key: run[key] for key in ("status", "revision", "note", "reviewed")
        },
    }
    return (
        json.dumps(packet, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
