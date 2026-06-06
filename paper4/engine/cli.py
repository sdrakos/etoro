"""eToro engine CLI: signal (dry-run) | execute (demo, gated) | retrain (admin).
Run from repo root: python paper4/engine/cli.py <cmd> [flags]."""
from __future__ import annotations
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "code")))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))   # repo root for back.*

from signal_engine import target_weights, train_full   # noqa: E402
from instrument_map import resolve, renormalize         # noqa: E402
from rebalancer import plan                              # noqa: E402
from etoro_adapter import EtoroAdapter                   # noqa: E402

CACHE = os.path.expanduser(os.path.join("~", ".etoro", "instrument_map.json"))


def _yahoo_fetch():
    from etf_data import load_etf_matrix
    close, _dates, tickers = load_etf_matrix()
    return close, tickers


def _load_cache():
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_cache(mp):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(mp, f)


def _real_client():
    from back.etoro_api.server import get_server_client
    return get_server_client()


def _search_fn(client):
    def search(ticker):
        r = client.request("GET", f"/api/v1/market-data/search?internalSymbolFull={ticker}")
        items = (r or {}).get("instruments") or (r or {}).get("data") or []
        return int(items[0]["instrumentId"]) if items else None
    return search


def cmd_signal(args, do_execute=False):
    weights = target_weights(args.strategy, fetch_close=_yahoo_fetch,
                             model_name=args.model)
    client = _real_client()
    mp, missing = resolve(list(weights), _search_fn(client), cache=_load_cache())
    _save_cache(mp)
    if missing:
        print(f"[warn] not on eToro, skipped: {missing}")
    weights = renormalize(weights, available=list(mp))
    adapter = EtoroAdapter(client, allow_execute=do_execute)
    current = adapter.positions()
    orders = plan(current, weights, mp, capital=args.capital, min_trade=args.min_trade)
    print(f"\nStrategy={args.strategy}  capital=EUR{args.capital:,.0f}  orders={len(orders)}")
    for o in orders:
        print(f"  {o.action.upper():<5} {o.ticker:<5} {'LONG' if o.is_buy else 'SHORT':<5} "
              f"EUR {o.amount_eur:>8,.0f}  ({o.reason})")
    if do_execute:
        print("\nExecuting on DEMO...")
        for o in orders:
            try:
                adapter.submit(o); print(f"  ok: {o.action} {o.ticker}")
            except Exception as e:
                print(f"  FAIL {o.action} {o.ticker}: {e}")
    else:
        print("\n(dry-run; pass `execute --execute` to send to demo)")


def cmd_retrain(args):
    close, tickers = _yahoo_fetch()
    print(f"training ML on {close.shape[0]} days x {len(tickers)} assets ...")
    train_full(close, tickers, name=args.model)
    print(f"saved frozen model '{args.model}' to ~/.etoro/models/")


def main():
    ap = argparse.ArgumentParser(prog="paper4-engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("signal", "execute"):
        p = sub.add_parser(name)
        p.add_argument("--strategy", choices=["rules", "ml"], default="rules")
        p.add_argument("--capital", type=float, default=10000.0)
        p.add_argument("--min-trade", type=float, default=50.0)
        p.add_argument("--model", default="prod")
        if name == "execute":
            p.add_argument("--execute", action="store_true")
    pr = sub.add_parser("retrain"); pr.add_argument("--model", default="prod")
    args = ap.parse_args()
    if args.cmd == "signal":
        cmd_signal(args, do_execute=False)
    elif args.cmd == "execute":
        cmd_signal(args, do_execute=args.execute)
    elif args.cmd == "retrain":
        cmd_retrain(args)


if __name__ == "__main__":
    main()
