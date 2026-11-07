"""Protected local bootstrap command: run interactively inside the API container."""

import argparse
import getpass
from datetime import date, time
from decimal import Decimal
from pathlib import Path

from app.config import get_settings
from app.historical.importer import import_fixture, orphan_files
from app.models import HistoricalPartition
from app.strategies.contracts import StrategyConfig
from app.strategy_evaluation import evaluate_fixture
from uuid import UUID

from sqlalchemy import select

from app.auth import password_hasher
from app.database import SessionLocal
from app.models import AuditLog, Instrument, ProviderSymbol, User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "bootstrap",
            "seed-demo",
            "import-candles",
            "historical-orphans",
            "evaluate-strategy",
        ],
    )
    parser.add_argument("--file", type=Path)
    parser.add_argument("--provider")
    parser.add_argument("--provider-key")
    parser.add_argument("--timeframe", choices=["1m", "5m"])
    parser.add_argument("--session-date", type=date.fromisoformat)
    parser.add_argument("--session-start", type=time.fromisoformat)
    parser.add_argument("--session-end", type=time.fromisoformat)
    parser.add_argument("--source-sha256")
    parser.add_argument("--job-id", type=UUID)
    parser.add_argument("--fast-period", type=int, default=3)
    parser.add_argument("--slow-period", type=int, default=5)
    parser.add_argument("--rsi-period", type=int, default=3)
    parser.add_argument("--rsi-floor", type=Decimal, default=Decimal("40"))
    parser.add_argument("--rsi-ceiling", type=Decimal, default=Decimal("100"))
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == "evaluate-strategy":
            if args.file is None or args.job_id is None:
                parser.error("evaluate-strategy requires --file and --job-id")
            result = evaluate_fixture(
                db,
                args.file,
                job_id=args.job_id,
                root=Path(get_settings().historical_data_root),
                config=StrategyConfig(
                    "option-premium-ema-rsi",
                    1,
                    args.fast_period,
                    args.slow_period,
                    args.rsi_period,
                    args.rsi_floor,
                    args.rsi_ceiling,
                ),
            )
            db.commit()
            print(
                f"Decision: {result.quality} {result.direction} reasons={result.reasons}"
            )
            return
        if args.command == "historical-orphans":
            catalog = set(db.scalars(select(HistoricalPartition.relative_path)).all())
            for relative in orphan_files(
                Path(get_settings().historical_data_root), catalog
            ):
                print(relative)
            return
        if args.command == "import-candles":
            if any(
                value is None
                for value in (
                    args.file,
                    args.provider,
                    args.provider_key,
                    args.timeframe,
                    args.session_date,
                    args.session_start,
                    args.session_end,
                    args.source_sha256,
                )
            ):
                parser.error(
                    "import-candles requires --file, --provider, --provider-key, --timeframe, --session-date, --session-start, --session-end and --source-sha256"
                )
            job = import_fixture(
                db,
                args.file,
                Path(get_settings().historical_data_root),
                provider=args.provider,
                provider_key=args.provider_key,
                timeframe=args.timeframe,
                session_date=args.session_date,
                session_start=args.session_start,
                session_end=args.session_end,
                source_sha256=args.source_sha256,
            )
            db.commit()
            print(
                f"Import {job.id}: {job.status}, rows={job.row_count}, duplicates={job.duplicate_count}, gaps={job.gap_count}"
            )
            return
        if args.command == "bootstrap":
            if db.scalar(select(User)):
                raise SystemExit("A user already exists; bootstrap refused")
            email = input("Administrator email: ").strip().lower()
            password = getpass.getpass("Password (minimum 14 characters): ")
            if "@" not in email or len(password) < 14:
                raise SystemExit(
                    "Valid email and password of at least 14 characters required"
                )
            db.add(User(email=email, password_hash=password_hasher.hash(password)))
            db.add(AuditLog(event_type="bootstrap"))
        else:
            for symbol, name, asset, exchange in [
                ("DEMO:NIFTY", "NIFTY 50 (DEMO)", "INDEX", "NSE"),
                ("DEMO:BANKNIFTY", "BANKNIFTY (DEMO)", "INDEX", "NSE"),
                ("DEMO:SENSEX", "SENSEX (DEMO)", "INDEX", "BSE"),
                ("DEMO:FINNIFTY", "FINNIFTY (DEMO)", "INDEX", "NSE"),
                (
                    "DEMO:OPTION",
                    "Illustrative option — not a real contract",
                    "OPTION",
                    "DEMO",
                ),
                ("DEMO:GOLD", "Gold placeholder (DEMO)", "COMMODITY", "DEMO"),
                ("DEMO:BTC", "BTC placeholder (DEMO)", "CRYPTO", "DEMO"),
            ]:
                existing = db.scalar(
                    select(Instrument).where(Instrument.canonical_symbol == symbol)
                )
                if existing:
                    if symbol == "DEMO:OPTION" and existing.is_demo:
                        existing.expiry_date = date(2030, 12, 31)
                        existing.strike_price = Decimal("100")
                        existing.option_type = "CE"
                    continue
                instrument = Instrument(
                    canonical_symbol=symbol,
                    display_name=name,
                    asset_class=asset,
                    exchange=exchange,
                    segment="DEMO",
                    expiry_date=date(2030, 12, 31) if asset == "OPTION" else None,
                    strike_price=Decimal("100") if asset == "OPTION" else None,
                    option_type="CE" if asset == "OPTION" else None,
                )
                db.add(instrument)
                db.flush()
                db.add(
                    ProviderSymbol(
                        instrument_id=instrument.id,
                        provider="DEMO",
                        provider_instrument_key=symbol,
                    )
                )
            db.add(AuditLog(event_type="demo_seed"))
        db.commit()


if __name__ == "__main__":
    main()
