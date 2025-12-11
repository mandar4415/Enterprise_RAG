"""Legacy migration shim.

The real migration script has been moved to `migrations/migrate_db.py`.
This shim imports and runs that script for backwards compatibility.
"""
from migrations import migrate_db


if __name__ == "__main__":
    migrate_db.migrate()
