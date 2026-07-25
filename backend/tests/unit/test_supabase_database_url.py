import importlib


def test_supabase_url_is_normalized_for_psycopg(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:password@db.example.supabase.co:5432/postgres")
    monkeypatch.setenv("JWT_SECRET_KEY", "a" * 64)

    import app.configuration as configuration
    import app.database as database

    configuration.get_settings.cache_clear()
    database = importlib.reload(database)

    assert database.DATABASE_URL.drivername == "postgresql+psycopg"
    assert database.DATABASE_URL.query["sslmode"] == "require"
    assert database.engine.url.drivername == "postgresql+psycopg"
