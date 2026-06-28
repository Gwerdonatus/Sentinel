"""
Management command: wait_for_db

Polls the database connection until it is available.
Used in Docker Compose to delay Django startup until PostgreSQL
is ready to accept connections — Docker's healthcheck alone is
not sufficient because pg_isready passes before PostgreSQL can
actually serve queries.

Usage:
    python manage.py wait_for_db
    python manage.py wait_for_db --timeout 60 --interval 2
"""

from __future__ import annotations

import time

import structlog
from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError, connections
from django.db.utils import DatabaseError

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Wait for the database to become available before proceeding."

    def add_arguments(self, parser: object) -> None:
        parser.add_argument(
            "--timeout",
            type=int,
            default=60,
            help="Maximum seconds to wait for the database (default: 60)",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=1.0,
            help="Seconds between connection attempts (default: 1.0)",
        )

    def handle(self, *args: object, **options: object) -> None:
        timeout: int = options["timeout"]  # type: ignore[assignment]
        interval: float = options["interval"]  # type: ignore[assignment]

        self.stdout.write("Waiting for database...")

        start = time.monotonic()
        attempt = 0

        while True:
            attempt += 1
            try:
                # Force a new connection attempt
                db_conn = connections["default"]
                db_conn.ensure_connection()
                elapsed = round(time.monotonic() - start, 1)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Database ready after {elapsed}s ({attempt} attempt(s))."
                    )
                )
                logger.info(
                    "database_ready",
                    elapsed_seconds=elapsed,
                    attempts=attempt,
                )
                return

            except (OperationalError, DatabaseError) as exc:
                elapsed = time.monotonic() - start

                if elapsed >= timeout:
                    raise CommandError(
                        f"Database not available after {timeout}s ({attempt} attempts). "
                        f"Last error: {exc}"
                    ) from exc

                logger.debug(
                    "database_not_ready",
                    attempt=attempt,
                    elapsed_seconds=round(elapsed, 1),
                    error=str(exc),
                )
                self.stdout.write(
                    f"  Attempt {attempt}: not ready ({round(elapsed, 1)}s elapsed). "
                    f"Retrying in {interval}s..."
                )
                time.sleep(interval)
