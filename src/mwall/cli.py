"""Command-line entry point: ``python -m mwall <stage>``.

Stages map to the Makefile targets. Every stage is resumable.
"""
from __future__ import annotations

import argparse
import sys
import time


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def cmd_index(args) -> None:
    from mwall.ingest import form_index
    from mwall.ingest.sec_client import SecClient

    df = form_index.build(SecClient(rate=args.rate))
    _log(f"form index rows kept: {len(df):,}; forms: {df['form'].value_counts().to_dict()}")


def cmd_discover(args) -> None:
    import pandas as pd

    from mwall.common import paths
    from mwall.ingest import discover
    from mwall.ingest.sec_client import SecClient

    idx = pd.read_parquet(paths.META_DIR / "form_index_abs.parquet")
    if not args.report_only:
        discover.probe_candidates(SecClient(rate=args.rate), idx, workers=args.workers, log=_log)
    trusts = discover.build_trusts(idx)
    _log(f"confirmed CMBS trusts: {len(trusts)}")
    _log(trusts.groupby("vintage").size().to_string())


def cmd_filings(args) -> None:
    from mwall.ingest import filings
    from mwall.ingest.sec_client import SecClient

    filings.run(SecClient(rate=args.rate), workers=args.workers, log=_log, limit=args.limit)


def cmd_download(args) -> None:
    from mwall.ingest import download
    from mwall.ingest.sec_client import SecClient

    download.run(SecClient(rate=args.rate), workers=args.workers, log=_log,
                 budget_s=args.budget_s, ciks=args.cik, max_filings=args.max_filings)


def cmd_tend(args) -> None:
    from mwall.ingest import tend
    from mwall.ingest.sec_client import SecClient

    tend.run(SecClient(rate=args.rate), workers=args.workers, per_agent=args.per_agent,
             budget_s=args.budget_s, log=_log)


def cmd_loandetail(args) -> None:
    if args.fetch:
        from mwall.ingest import loan_detail as ld
        from mwall.ingest.sec_client import SecClient

        agents = None if args.all_agents else ld.PILOT_AGENTS
        ld.fetch(SecClient(rate=args.rate), workers=args.workers, agents=agents, budget_s=args.budget_s, log=_log)
    if args.parse:
        from mwall.parse import loan_detail as pld

        pld.run(log=_log)
        pld.maturity_outcomes(log=_log)


def cmd_panel(args) -> None:
    from mwall.panel import build

    build.build(log=_log)


def cmd_census(args) -> None:
    from mwall.parse import census

    census.run(sample_per_group=args.per_group, log=_log)


def cmd_parse(args) -> None:
    from mwall.parse import write

    write.run(log=_log, workers=args.workers, ciks=args.cik)


def cmd_clean(args) -> None:
    from mwall.clean import run

    run.run(log=_log, workers=args.workers, ciks=args.cik)


def cmd_wholeloans(args) -> None:
    from mwall.clean import whole_loans

    whole_loans.build(log=_log)


def cmd_geo(args) -> None:
    from mwall.clean import geography

    geography.build(budget_s=args.budget_s, log=_log)


def cmd_crosscheck(args) -> None:
    from mwall.parse import crosscheck

    crosscheck.run(n=args.n, log=_log)


def cmd_fixture(args) -> None:
    from mwall import fixture

    if args.make:
        fixture.make()
    ok = fixture.build(update=args.update, log=_log)
    sys.exit(0 if ok else 1)


def cmd_qa(args) -> None:
    from mwall.clean import qa_report

    qa_report.run(log=_log)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="mwall")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("index", help="download EDGAR quarterly indexes, keep 10-D and ABS-EE rows")
    s.add_argument("--rate", type=float, default=6.0)
    s.set_defaults(func=cmd_index)

    s = sub.add_parser("discover", help="probe ABS-EE filers' EX-102 namespace; write trusts table")
    s.add_argument("--rate", type=float, default=6.0)
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--report-only", action="store_true")
    s.set_defaults(func=cmd_discover)

    s = sub.add_parser("filings", help="enumerate 10-D/ABS-EE filings per trust from submissions JSON")
    s.add_argument("--rate", type=float, default=6.0)
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--limit", type=int, default=None)
    s.set_defaults(func=cmd_filings)

    s = sub.add_parser("download", help="download EX-102/EX-103 for every ABS-EE filing (resumable)")
    s.add_argument("--rate", type=float, default=6.0)
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--budget-s", type=float, default=None, help="stop cleanly after this many seconds")
    s.add_argument("--cik", type=int, action="append", help="restrict to these trust CIKs")
    s.add_argument("--max-filings", type=int, default=None)
    s.set_defaults(func=cmd_download)

    s = sub.add_parser("panel", help="loan-month panel and tier 1-3 outcome labels (docs/labels.md)")
    s.set_defaults(func=cmd_panel)

    s = sub.add_parser("loandetail", help="vintage-2016 10-D loan detail tables (D033 pilot): fetch and/or parse")
    s.add_argument("--fetch", action="store_true")
    s.add_argument("--parse", action="store_true")
    s.add_argument("--all-agents", action="store_true", help="beyond the Computershare pilot")
    s.add_argument("--rate", type=float, default=7.0)
    s.add_argument("--workers", type=int, default=8)
    s.add_argument("--budget-s", type=float, default=None)
    s.set_defaults(func=cmd_loandetail)

    s = sub.add_parser("tend", help="fetch 10-D distribution statements and extract pool balances")
    s.add_argument("--rate", type=float, default=6.0)
    s.add_argument("--workers", type=int, default=8)
    s.add_argument("--per-agent", type=int, default=None, help="sample this many statements per filer agent")
    s.add_argument("--budget-s", type=float, default=None)
    s.set_defaults(func=cmd_tend)

    s = sub.add_parser("census", help="tag census over a stratified sample of raw files")
    s.add_argument("--per-group", type=int, default=3)
    s.set_defaults(func=cmd_census)

    s = sub.add_parser("parse", help="parse raw XML to parquet")
    s.add_argument("--workers", type=int, default=2)
    s.add_argument("--cik", type=int, action="append")
    s.set_defaults(func=cmd_parse)

    s = sub.add_parser("clean", help="resolve layouts, decode, flag: loan_period and property_period")
    s.add_argument("--workers", type=int, default=3)
    s.add_argument("--cik", type=int, action="append")
    s.set_defaults(func=cmd_clean)

    s = sub.add_parser("wholeloans", help="group pari passu pieces across trusts into whole loans")
    s.set_defaults(func=cmd_wholeloans)

    s = sub.add_parser("geo", help="geocode property addresses; county and metro from Census crosswalks")
    s.add_argument("--budget-s", type=float, default=None, help="stop sending geocoder batches after this many seconds")
    s.set_defaults(func=cmd_geo)

    s = sub.add_parser("crosscheck", help="compare our parser with edgartools on N filings (dev dependency)")
    s.add_argument("--n", type=int, default=20)
    s.set_defaults(func=cmd_crosscheck)

    s = sub.add_parser("fixture", help="build the committed fixture dataset and compare with stored outputs")
    s.add_argument("--make", action="store_true", help="re-copy fixture inputs from data/ (maintainer)")
    s.add_argument("--update", action="store_true", help="overwrite the stored expected outputs")
    s.set_defaults(func=cmd_fixture)

    s = sub.add_parser("qa", help="write the Gate 1 QA and field-coverage reports to docs/qa")
    s.set_defaults(func=cmd_qa)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
