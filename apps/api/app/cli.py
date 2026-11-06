"""Protected local bootstrap command: run interactively inside the API container."""

import argparse
import getpass

from sqlalchemy import select

from app.auth import password_hasher
from app.database import SessionLocal
from app.models import AuditLog, Instrument, ProviderSymbol, User


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["bootstrap", "seed-demo"])
    args = parser.parse_args()
    with SessionLocal() as db:
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
                if db.scalar(
                    select(Instrument).where(Instrument.canonical_symbol == symbol)
                ):
                    continue
                instrument = Instrument(
                    canonical_symbol=symbol,
                    display_name=name,
                    asset_class=asset,
                    exchange=exchange,
                    segment="DEMO",
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
