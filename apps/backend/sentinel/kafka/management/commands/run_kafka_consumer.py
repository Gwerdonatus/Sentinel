"""Management command: run_kafka_consumer"""

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Start the Sentinel Kafka consumer process."

    def add_arguments(self, parser: object) -> None:
        parser.add_argument("--topics", nargs="+", default=None)
        parser.add_argument("--group-id", default=None)

    def handle(self, *args: object, **options: object) -> None:
        from sentinel.kafka.consumer import SentinelKafkaConsumer

        topics = options["topics"] or ["sentinel.default.audit.events"]
        group_id = options["group_id"] or f"sentinel-risk-engine-{settings.ENVIRONMENT}"

        self.stdout.write(self.style.SUCCESS(
            f"Starting Kafka consumer | Topics: {topics} | Group: {group_id}"
        ))

        SentinelKafkaConsumer(topics=topics, group_id=group_id).start()
