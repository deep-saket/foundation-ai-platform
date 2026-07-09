# `alembic/` — Database Migrations

Alembic migration environment for managing the platform's relational database schema. Supports both online (live connection) and offline (SQL script generation) migration modes.

---

## Files

### `env.py` — Migration Environment Configuration

Configures Alembic to use the platform's database URL, either from explicit configuration or by loading `configs/platform.yaml`.

| Function | Signature | Use Case |
|---|---|---|
| `_resolve_database_url` | `() → str` | Resolves the SQLAlchemy database URL. First checks `alembic.ini` for an explicit `sqlalchemy.url`, then falls back to loading `PlatformConfig` via `ConfigLoader`. |
| `run_migrations_offline` | `() → None` | Generates SQL migration scripts without a live database connection. Useful for review or manual execution. |
| `run_migrations_online` | `() → None` | Connects to the database and applies migrations transactionally. Uses `NullPool` to avoid connection pooling during migrations. |

### `script.py.mako`

Mako template for generating new migration revision files via `alembic revision`.

### `versions/`

Directory containing individual migration scripts. Each migration file represents a schema change (table creation, column addition, etc.).

---

## Usage

```bash
# Run all pending migrations
alembic upgrade head

# Generate a new migration
alembic revision --autogenerate -m "description of change"

# Downgrade one revision
alembic downgrade -1

# Show current revision
alembic current
```

---

## Configuration

The migration environment reads the database URL from `configs/platform.yaml` by default. Override via:

- `alembic.ini` → `sqlalchemy.url` setting
- `platform_config_path` main option (set by `scripts/bootstrap.py`)
