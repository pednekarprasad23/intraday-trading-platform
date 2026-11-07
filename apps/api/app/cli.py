"""Protected local bootstrap command: run interactively inside the API container."""

import argparse
import getpass
import os
import tempfile
from datetime import date, time
from decimal import Decimal
from pathlib import Path

from app.config import get_settings
from app.historical.credentials import (
    CredentialError,
    delete_dhan_token,
    initialize_key,
    load_dhan_token,
    store_dhan_token,
)
from app.historical.importer import import_fixture, orphan_files
from app.historical.dhan import ExactIdentity, fetch_exact, fetch_rolling
from app.historical.reader import read_sessions
from app.backtesting.engine import SimulationConfig, run
from app.backtesting.walk_forward import walk_forward
from app.backtesting.reports import persist_backtest, persist_walk_forward
from app.models import HistoricalPartition
from app.strategies.contracts import StrategyConfig
from app.strategy_evaluation import evaluate_catalog, evaluate_fixture
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
            "evaluate-catalog",
            "backtest",
            "walk-forward",
            "dhan-exact-import",
            "dhan-rolling-check",
            "credential-init",
            "credential-save-dhan",
            "credential-delete-dhan",
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
    parser.add_argument("--instrument-id", type=UUID)
    parser.add_argument("--dates", type=date.fromisoformat, nargs="+")
    parser.add_argument("--quantity", type=Decimal, default=Decimal("1"))
    parser.add_argument("--fee-per-side", type=Decimal, default=Decimal("0"))
    parser.add_argument("--tax-rate", type=Decimal, default=Decimal("0"))
    parser.add_argument("--slippage", type=Decimal, default=Decimal("0"))
    parser.add_argument("--spread", type=Decimal, default=Decimal("0"))
    parser.add_argument("--stop-fraction", type=Decimal, default=Decimal("0.1"))
    parser.add_argument("--target-fraction", type=Decimal, default=Decimal("0.2"))
    parser.add_argument("--train-size", type=int, default=2)
    parser.add_argument("--test-size", type=int, default=1)
    parser.add_argument("--security-id")
    parser.add_argument("--exchange-segment")
    parser.add_argument("--instrument-kind")
    parser.add_argument("--expiry", type=date.fromisoformat)
    parser.add_argument("--strike", type=Decimal)
    parser.add_argument("--option-type", choices=["CE", "PE"])
    parser.add_argument("--expiry-flag", choices=["WEEK", "MONTH"])
    parser.add_argument("--expiry-code", type=int)
    parser.add_argument("--relative-strike")
    args = parser.parse_args()
    if args.command.startswith("credential-"):
        key_path = Path(get_settings().credential_key_path)
        try:
            if args.command == "credential-init":
                initialize_key(key_path)
                print("Credential key initialized; retain an offline protected backup")
            elif args.command == "credential-save-dhan":
                token = getpass.getpass("Dhan access token (hidden): ")
                with SessionLocal() as db:
                    store_dhan_token(db, key_path, token)
                del token
                print(
                    "Dhan read-only data token stored encrypted; previous token replaced"
                )
            else:
                with SessionLocal() as db:
                    delete_dhan_token(db)
                print("Stored Dhan token deleted")
        except CredentialError as exc:
            parser.error(str(exc))
        return
    if args.command in {"dhan-exact-import", "dhan-rolling-check"}:
        required = (
            args.security_id,
            args.exchange_segment,
            args.instrument_kind,
            args.timeframe,
            args.session_date,
            args.session_start,
            args.session_end,
        )
        if any(value is None for value in required):
            parser.error(
                "Dhan history requires explicit security ID, exchange segment, instrument kind, timeframe and IST session window"
            )
        # An explicit ephemeral override is useful for isolated verification;
        # ordinary operator runs decrypt the stored credential only here.
        token = os.environ.get("DHAN_ACCESS_TOKEN")
        if not token:
            try:
                with SessionLocal() as credential_db:
                    token = load_dhan_token(
                        credential_db, Path(get_settings().credential_key_path)
                    )
            except CredentialError as exc:
                parser.error(str(exc))
        if args.command == "dhan-rolling-check":
            if (
                args.expiry_flag is None
                or args.expiry_code is None
                or args.relative_strike is None
                or args.option_type is None
            ):
                parser.error(
                    "Rolling check requires expiry flag/code, relative strike and option type"
                )
            result = fetch_rolling(
                security_id=args.security_id,
                exchange_segment=args.exchange_segment,
                instrument=args.instrument_kind,
                expiry_flag=args.expiry_flag,
                expiry_code=args.expiry_code,
                strike=args.relative_strike,
                option_type="CALL" if args.option_type == "CE" else "PUT",
                timeframe=args.timeframe,
                session_date=args.session_date,
                session_start=args.session_start,
                session_end=args.session_end,
                token=token,
            )
            print(
                f"ROLLING RESEARCH ONLY: bars={len(result.ce) + len(result.pe)} gaps={len(result.ce_gaps) + len(result.pe_gaps)} source_sha256={result.provenance.source_sha256}; never an exact-contract backtest"
            )
            return
        if (
            args.provider_key != args.security_id
            or args.instrument_id is None
            or args.expiry is None
            or args.strike is None
            or args.option_type is None
        ):
            parser.error(
                "Exact import requires matching --provider-key/--security-id and externally verified --instrument-id --expiry --strike --option-type"
            )
        with SessionLocal() as db:
            instrument = db.get(Instrument, args.instrument_id)
            mapping = db.scalar(
                select(ProviderSymbol).where(
                    ProviderSymbol.instrument_id == args.instrument_id,
                    ProviderSymbol.provider == "DHAN",
                    ProviderSymbol.provider_instrument_key == args.security_id,
                )
            )
            if (
                instrument is None
                or mapping is None
                or instrument.is_demo
                or instrument.metadata_source != "DHAN"
                or mapping.last_verified_at is None
                or mapping.provider_exchange != args.exchange_segment
                or args.instrument_kind != "OPTIDX"
                or instrument.asset_class != "OPTION"
                or instrument.underlying_id is None
                or instrument.expiry_date != args.expiry
                or instrument.strike_price != args.strike
                or instrument.option_type != args.option_type
            ):
                raise ValueError(
                    "Verified exact Dhan instrument and mapping required before fetching"
                )
            result = fetch_exact(
                identity=ExactIdentity(
                    args.security_id,
                    args.provider_key,
                    args.expiry,
                    args.strike,
                    args.option_type,
                    args.session_date,
                    args.session_start,
                    args.session_end,
                    True,
                ),
                exchange_segment=args.exchange_segment,
                instrument=args.instrument_kind,
                timeframe=args.timeframe,
                token=token,
            )
            if result.gaps or result.duplicate_count:
                raise ValueError(
                    "Dhan source gaps/duplicates require operator review; no import"
                )
            # The Phase 3 importer hashes normalized CSV bytes; the original
            # sanitized provider-response hash is separately reported to the operator.
            with tempfile.TemporaryDirectory(prefix="dhan-history-") as folder:
                fixture = Path(folder) / "verified.csv"
                fixture.write_bytes(result.fixture)
                job = import_fixture(
                    db,
                    fixture,
                    Path(get_settings().historical_data_root),
                    provider="DHAN",
                    provider_key=args.provider_key,
                    timeframe=args.timeframe,
                    session_date=args.session_date,
                    session_start=args.session_start,
                    session_end=args.session_end,
                    source_sha256=result.fixture_sha256,
                )
                if (
                    job.provider_response_sha256 is not None
                    and job.provider_response_sha256 != result.provenance.source_sha256
                ):
                    raise ValueError(
                        "Existing import has different provider response; operator review required"
                    )
                job.provider_response_sha256 = result.provenance.source_sha256
                job.provider_retrieved_at = result.provenance.retrieved_at
                db.commit()
            print(
                f"DHAN EXACT RESEARCH ONLY: job={job.id} rows={job.row_count} normalized_sha256={result.fixture_sha256} provider_response_sha256={result.provenance.source_sha256}"
            )
        return
    with SessionLocal() as db:
        if args.command in {"backtest", "walk-forward"}:
            if (
                not args.provider
                or not args.instrument_id
                or not args.timeframe
                or not args.dates
            ):
                parser.error(
                    "backtest/walk-forward requires --provider --instrument-id --timeframe --dates"
                )
            sessions = read_sessions(
                db,
                Path(get_settings().historical_data_root),
                provider=args.provider,
                instrument_id=args.instrument_id,
                timeframe=args.timeframe,
                dates=tuple(args.dates),
            )
            strategy = StrategyConfig(
                "option-premium-ema-rsi",
                1,
                args.fast_period,
                args.slow_period,
                args.rsi_period,
                args.rsi_floor,
                args.rsi_ceiling,
            )
            simulation = SimulationConfig(
                args.quantity,
                args.fee_per_side,
                args.tax_rate,
                args.slippage,
                args.spread,
                args.stop_fraction,
                args.target_fraction,
            )
            if args.command == "backtest":
                result = run(sessions, strategy, simulation)
                report = persist_backtest(db, sessions, strategy, simulation, result)
                db.commit()
                print(
                    f"RESEARCH ONLY / SIMULATED / NO BROKER ORDER: report={report.id} fingerprint={result.fingerprint} metrics={result.metrics}"
                )
                for trade in result.trades:
                    print(trade)
            else:
                folds = walk_forward(
                    sessions,
                    (strategy,),
                    simulation,
                    train_size=args.train_size,
                    test_size=args.test_size,
                )
                report = persist_walk_forward(
                    db,
                    sessions,
                    strategy,
                    simulation,
                    folds,
                    args.train_size,
                    args.test_size,
                )
                db.commit()
                print(
                    f"RESEARCH ONLY / SIMULATED / NO BROKER ORDER: report={report.id}"
                )
                for fold in folds:
                    print(
                        f"SIMULATED OOS: train={fold.training_dates} test={fold.test_dates} "
                        f"chosen={fold.chosen} metrics={fold.test.metrics} "
                        f"fingerprint={fold.test.fingerprint}"
                    )
            return
        if args.command == "evaluate-catalog":
            if (
                not args.instrument_id
                or not args.provider
                or not args.timeframe
                or not args.session_date
            ):
                parser.error(
                    "evaluate-catalog requires --instrument-id --provider --timeframe --session-date"
                )
            result = evaluate_catalog(
                db,
                root=Path(get_settings().historical_data_root),
                instrument_id=args.instrument_id,
                provider=args.provider,
                timeframe=args.timeframe,
                session_date=args.session_date,
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
                f"RESEARCH ONLY / NO BROKER ORDER: decision={result.quality} {result.direction} reasons={result.reasons}"
            )
            return
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
