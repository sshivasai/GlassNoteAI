# Database Migrations

This project uses Alembic for database schema migrations.

## Quick Start

### Run pending migrations
```bash
cd backend
python run_migrations.py
```

### Check current migration status
```bash
python run_migrations.py current
```

### View migration history
```bash
python run_migrations.py history
```

## Creating New Migrations

### Auto-generate migration from model changes
```bash
alembic revision --autogenerate -m "description of changes"
```

### Create empty migration (for data migrations)
```bash
alembic revision -m "description of changes"
```

Then edit the generated file in `alembic/versions/` to add your migration logic.

## Migration Order

Current migrations (in order):
1. `001_add_user_profile_columns.py` - Add user profile and Google OAuth columns
2. `002_add_plan_expires_at.py` - Add plan expiration tracking
3. `003_add_sessions_columns.py` - Add session summary and conversation storage
4. `004_add_byok_enabled.py` - Add BYOK feature toggle and migrate BYOK users

## Direct Alembic Commands

```bash
# Upgrade to latest
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Downgrade one version
alembic downgrade -1

# Show current version
alembic current

# Show history
alembic history

# Show SQL without executing
alembic upgrade head --sql
```

## Production Deployment

1. Always backup your database before running migrations
2. Test migrations on a staging database first
3. Run `python run_migrations.py` as part of your deployment process
4. Monitor for errors during migration

## Notes

- Migrations run automatically during startup in development
- In production, run migrations manually before deploying new code
- Never edit existing migration files that have been applied
- Use `downgrade()` for rollback capability
