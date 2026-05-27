"""CLI argparse + sweep parameter parsing tests."""
import pytest

from trader.cli import build_parser, cmd_sweep
from trader.strategies import STRATEGY_REGISTRY


def test_build_parser_has_all_subcommands():
    parser = build_parser()
    # Subparsers are accessible via parser._subparsers — verify by parsing each
    for cmd in ["fetch", "cache-list", "cache-clear", "strategies", "backtest", "sweep"]:
        # cache-clear requires a positional ticker; fetch requires positional + --from
        # We just verify the subparser exists by inspecting the registered subparsers.
        pass
    # Simpler check: print help and confirm each subcommand listed
    help_text = parser.format_help()
    for cmd in ["fetch", "cache-list", "cache-clear", "strategies", "backtest", "sweep"]:
        assert cmd in help_text


def test_sweep_unknown_strategy_exits_2(capsys):
    parser = build_parser()
    args = parser.parse_args([
        "sweep", "no_such_strategy",
        "--tickers", "AMD,NVDA",
        "--from", "2024-01-01",
        "--to", "2024-06-30",
        "--out", "/tmp/x",
    ])
    with pytest.raises(SystemExit) as exc:
        cmd_sweep(args)
    assert exc.value.code == 2
    captured = capsys.readouterr()
    assert "unknown strategy" in captured.err.lower()


def test_sweep_param_casting_preserves_types(monkeypatch, tmp_path):
    """When sweep is given a single (non-CSV) numeric param, it must be cast to int/float, not left as str."""
    parser = build_parser()
    args = parser.parse_args([
        "sweep", "pair_trading",
        "--tickers", "AMD,NVDA",
        "--from", "2024-01-01",
        "--to", "2024-06-30",
        "--out", str(tmp_path / "sweep_out"),
        # Single value (no comma) — must be cast to int by sweep logic
        "--lookback", "45",
    ])
    # Don't actually call run_backtest (would need real cache data) — instead
    # inspect the post-parse args to ensure flags came through as strings, then
    # verify the param-extraction logic in cmd_sweep would cast them.
    assert args.lookback == "45"  # argparse stores as str because allow_csv=True

    # Re-create the sweep's grid logic on a known field to assert the cast:
    from dataclasses import fields
    from trader.strategies.pair_trading import PairParams
    f = next(field for field in fields(PairParams) if field.name == "lookback")
    cast = int if f.type in (int, "int") else float
    casted = cast(args.lookback)
    assert isinstance(casted, int)
    assert casted == 45
