"""
Run Alembic migrations programmatically.

Usage:
    python run_migrations.py          # Run all pending migrations
    python run_migrations.py --help   # Show available commands
"""
import sys
from alembic.config import Config
from alembic import command


def run_migrations():
    """Run all pending Alembic migrations."""
    alembic_cfg = Config("alembic.ini")

    print("[migrations] Running Alembic migrations...")
    try:
        command.upgrade(alembic_cfg, "head")
        print("[migrations] ✓ Migrations applied successfully")
    except Exception as e:
        print(f"[migrations] ✗ Migration failed: {e}")
        sys.exit(1)


def show_current():
    """Show current migration revision."""
    alembic_cfg = Config("alembic.ini")
    command.current(alembic_cfg)


def show_history():
    """Show migration history."""
    alembic_cfg = Config("alembic.ini")
    command.history(alembic_cfg)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "current":
            show_current()
        elif cmd == "history":
            show_history()
        elif cmd == "--help":
            print("Usage:")
            print("  python run_migrations.py         # Run all pending migrations")
            print("  python run_migrations.py current # Show current revision")
            print("  python run_migrations.py history # Show migration history")
        else:
            print(f"Unknown command: {cmd}")
            print("Use --help for available commands")
    else:
        run_migrations()
