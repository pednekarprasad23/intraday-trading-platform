from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_migration_roundtrip(tmp_path, monkeypatch):
    from app.config import get_settings

    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "head")
        assert "instruments" in inspect(create_engine(url)).get_table_names()
        assert "historical_partitions" in inspect(create_engine(url)).get_table_names()
        assert "strategy_signals" in inspect(create_engine(url)).get_table_names()
        command.downgrade(config, "0003_historical_candles")
        assert "strategy_signals" not in inspect(create_engine(url)).get_table_names()
        command.upgrade(config, "head")
        command.downgrade(config, "0002_market_metadata")
        assert (
            "historical_partitions" not in inspect(create_engine(url)).get_table_names()
        )
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        assert "instruments" not in inspect(create_engine(url)).get_table_names()
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()
