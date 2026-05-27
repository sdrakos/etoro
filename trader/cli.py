"""CLI: python -m trader {fetch | cache-list | cache-clear | strategies | backtest | sweep}."""
from __future__ import annotations
import argparse
import dataclasses
import itertools
import json
import sys
from dataclasses import fields
from datetime import date, datetime
from pathlib import Path

from trader.config import CACHE_DB
from trader.data.cache import Cache
from trader.data.loader import load_bars
from trader.strategies import STRATEGY_REGISTRY  # triggers auto-import


def _parse_date(s: str) -> date:
    if s.lower() == "today":
        return date.today()
    return datetime.fromisoformat(s).date()


def cmd_fetch(args):
    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    start = _parse_date(args.from_)
    end = _parse_date(args.to)
    for t in tickers:
        df = load_bars(t, start, end, timespan=args.timespan)
        print(f"{t}: {len(df)} bars  {df.index.min() if not df.empty else '—'} → {df.index.max() if not df.empty else '—'}")


def cmd_cache_list(args):
    cache = Cache(CACHE_DB)
    df = cache.list_tickers(timespan=args.timespan)
    if df.empty:
        print("(empty cache)")
        return
    import pandas as pd
    df["min_date"] = pd.to_datetime(df["min_ts"], unit="ms").dt.date
    df["max_date"] = pd.to_datetime(df["max_ts"], unit="ms").dt.date
    print(df[["ticker", "min_date", "max_date", "bar_count"]].to_string(index=False))


def cmd_cache_clear(args):
    cache = Cache(CACHE_DB)
    n = cache.clear(args.ticker.upper(), timespan=args.timespan)
    print(f"deleted {n} rows for {args.ticker.upper()}")


def cmd_strategies(args):
    if not STRATEGY_REGISTRY:
        print("(no strategies registered)")
        return
    width = max(len(n) for n in STRATEGY_REGISTRY) + 2
    for name, cls in sorted(STRATEGY_REGISTRY.items()):
        print(f"{name:<{width}} {cls.description}")


def cmd_backtest(args):
    from trader.engine import run_backtest, write_report

    strat_cls = STRATEGY_REGISTRY.get(args.strategy)
    if not strat_cls:
        print(f"unknown strategy: {args.strategy}", file=sys.stderr)
        print("Available:", ", ".join(STRATEGY_REGISTRY), file=sys.stderr)
        sys.exit(2)

    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    params = {f.name: getattr(args, f.name.replace("-", "_"), f.default)
              for f in fields(strat_cls.params_dataclass)
              if f.name != "tickers"}
    params["tickers"] = tuple(tickers)

    result = run_backtest(
        strategy_cls=strat_cls,
        params=params,
        tickers=tickers,
        start=_parse_date(args.from_),
        end=_parse_date(args.to),
        capital=args.capital,
    )
    out = write_report(result, args.out)
    print(f"\nResults written to {out}")
    print(json.dumps(result.metrics, indent=2))


def cmd_sweep(args):
    """Grid search over comma-separated parameter values."""
    from trader.engine import run_backtest, write_report

    strat_cls = STRATEGY_REGISTRY.get(args.strategy)
    if not strat_cls:
        print(f"unknown strategy: {args.strategy}", file=sys.stderr)
        print("Available:", ", ".join(STRATEGY_REGISTRY), file=sys.stderr)
        sys.exit(2)

    grid = {}
    for f in fields(strat_cls.params_dataclass):
        if f.name == "tickers":
            continue
        val = getattr(args, f.name.replace("-", "_"), None)
        cast = int if f.type in (int, "int") else float
        if isinstance(val, str) and "," in val:
            grid[f.name] = [cast(x) for x in val.split(",")]
        elif val is not None:
            grid[f.name] = [cast(val) if isinstance(val, str) else val]

    keys = list(grid)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = []

    for combo in itertools.product(*[grid[k] for k in keys]):
        params = dict(zip(keys, combo))
        params["tickers"] = tuple(t.strip().upper() for t in args.tickers.split(","))
        slug = "_".join(f"{k}{v}" for k, v in zip(keys, combo))
        result = run_backtest(
            strategy_cls=strat_cls, params=params,
            tickers=list(params["tickers"]),
            start=_parse_date(args.from_), end=_parse_date(args.to),
            capital=args.capital,
        )
        write_report(result, out_dir / slug)
        summary.append({"params": params, "metrics": result.metrics})
        print(f"  {slug}  sharpe={result.metrics.get('sharpe')}  trades={result.metrics.get('total_trades')}")

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\n{len(summary)} runs written to {out_dir}")


def _attach_strategy_flags(subparser, allow_csv: bool = False):
    """Add per-strategy flags by inspecting each registered dataclass.

    `allow_csv=True` keeps types as str so the sweep command can pass comma lists.
    """
    seen = set()
    for cls in STRATEGY_REGISTRY.values():
        for f in fields(cls.params_dataclass):
            if f.name in seen or f.name == "tickers":
                continue
            seen.add(f.name)
            flag = "--" + f.name.replace("_", "-")
            if allow_csv:
                subparser.add_argument(flag, type=str, default=str(f.default))
            elif f.type is int or f.type == "int":
                subparser.add_argument(flag, type=int, default=f.default)
            elif f.type is float or f.type == "float":
                subparser.add_argument(flag, type=float, default=f.default)
            else:
                subparser.add_argument(flag, type=str, default=f.default)


def build_parser():
    p = argparse.ArgumentParser(prog="trader")
    sp = p.add_subparsers(dest="cmd", required=True)

    pf = sp.add_parser("fetch", help="Preload cache with bars from Massive")
    pf.add_argument("tickers", help="comma-separated tickers, e.g. AMD,NVDA")
    pf.add_argument("--from", dest="from_", required=True)
    pf.add_argument("--to", default="today")
    pf.add_argument("--timespan", default="day")
    pf.set_defaults(func=cmd_fetch)

    pl = sp.add_parser("cache-list", help="Show what's in the cache")
    pl.add_argument("--timespan", default="day")
    pl.set_defaults(func=cmd_cache_list)

    pc = sp.add_parser("cache-clear", help="Delete bars for one ticker")
    pc.add_argument("ticker")
    pc.add_argument("--timespan", default="day")
    pc.set_defaults(func=cmd_cache_clear)

    ps = sp.add_parser("strategies", help="List registered strategies")
    ps.set_defaults(func=cmd_strategies)

    pb = sp.add_parser("backtest", help="Run one backtest config")
    pb.add_argument("strategy")
    pb.add_argument("--tickers", required=True)
    pb.add_argument("--from", dest="from_", required=True)
    pb.add_argument("--to", required=True)
    pb.add_argument("--capital", type=float, default=100_000)
    pb.add_argument("--out", required=True)
    _attach_strategy_flags(pb)
    pb.set_defaults(func=cmd_backtest)

    psw = sp.add_parser("sweep", help="Grid-search a strategy")
    psw.add_argument("strategy")
    psw.add_argument("--tickers", required=True)
    psw.add_argument("--from", dest="from_", required=True)
    psw.add_argument("--to", required=True)
    psw.add_argument("--capital", type=float, default=100_000)
    psw.add_argument("--out", required=True)
    _attach_strategy_flags(psw, allow_csv=True)
    psw.set_defaults(func=cmd_sweep)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
