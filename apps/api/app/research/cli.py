"""python -m app.research.cli --help"""

import argparse
from datetime import datetime, timezone
import json

from app.artifacts import read_json, write_json
from app.database import engine
from app.research.dataset import code_identity, export_dataset, utc
from app.research.evaluation import evaluate, legacy_diagnostic
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser(description="Immutable, observation-time research")
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser("snapshot")
    snapshot.add_argument("--as-of", help="Timezone-aware cutoff; defaults to the actual export time")
    run = commands.add_parser("evaluate")
    run.add_argument("--dataset", required=True, help="Content-addressed dataset SHA-256")
    run.add_argument("--validation-start", required=True)
    run.add_argument("--test-start", required=True)
    args = parser.parse_args()
    if args.command == "snapshot":
        cutoff = utc(args.as_of) if args.as_of else datetime.now(timezone.utc)
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            with connection.begin():
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                with Session(bind=connection) as db:
                    key, dataset = export_dataset(db,cutoff)
        print(json.dumps({"dataset_sha256":key,"as_of":dataset["as_of"],"rows":len(dataset["rows"])}))
    else:
        dataset = read_json("datasets",args.dataset)
        report = evaluate(dataset,args.validation_start,args.test_start)
        report["legacy_diagnostic"] = legacy_diagnostic(dataset)
        report.update({"dataset_sha256":args.dataset,"code":code_identity(),"protocol":"observed-v1"})
        key = write_json("reports",report)
        print(json.dumps({"report_sha256":key,"status":report["status"],"blocker":report["blocker"],
                          "exclusions":report["exclusions"],
                          "models":{name:value["test"] for name,value in report["models"].items()}},indent=2))


if __name__ == "__main__":
    main()
