"""
Management command: run_kafka_consumer

Starts the Sentinel Kafka consumer as a long-lived process.
Designed to run as a separate Docker service in production.

Usage:
    python manage.py run_kafka_consumer
    python manage.py run_kafka_consumer --topics sentinel.default.audit.events
    python manage.py run_kafka_consumer --group-id my-consumer-group
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Start the Sentinel Kafka consumer process."

    def add_arguments(self, parser: object) -> None:
        parser.add_argument(
            "--topics",
            nargs="+",
            default=None,
            help="Kafka topics to subscribe to. Defaults to all audit event topics.",
        )
        parser.add_argument(
            "--group-id",
            default=None,
            help="Consumer group ID. Defaults to sentinel-risk-engine-{environment}.",
        )

    def handle(self, *args: object, **options: object) -> None:
        from sentinel.kafka.consumer import SentinelKafkaConsumer

        topics = options["topics"] or [
            "sentinel.default.audit.events",  # Single-tenant / default
        ]
        group_id = options["group_id"] or f"sentinel-risk-engine-{settings.ENVIRONMENT}"

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting Kafka consumer\n"
                f"  Topics: {topics}\n"
                f"  Group:  {group_id}\n"
                f"  Press Ctrl+C to stop."
            )
        )

        consumer = SentinelKafkaConsumer(topics=topics, group_id=group_id)
        consumer.start()
