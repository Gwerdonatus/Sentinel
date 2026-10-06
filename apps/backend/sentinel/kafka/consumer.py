"""
Sentinel Kafka Consumer.

Long-running process that subscribes to audit event topics and
feeds events into the risk scoring pipeline.

RUN AS:
    python manage.py run_kafka_consumer

CONSUMER GROUP:
    Group ID: sentinel-risk-engine-{environment}

    Multiple worker instances with the same group ID share the partition
    load automatically. Kafka guarantees each partition is consumed by
    exactly one group member at a time — ordering within a partition
    is preserved.

PARTITION STRATEGY:
    Events are partitioned by actor_id (or agent_name for AI agents).
    This ensures all events from the same actor are processed in order
    by the same consumer instance, which matters for:
    - Velocity spike detection (needs sequential event ordering)
    - Behavioral baseline computation (needs consistent history)

OFFSET MANAGEMENT:
    Offsets are committed after successful processing (enable.auto.commit=false).
    If the risk engine fails, the offset is not committed — the event
    will be reprocessed on restart. This gives at-least-once semantics.
    The risk engine is idempotent for the same event_id so reprocessing
    is safe (score is overwritten, not doubled).
"""

from __future__ import annotations

import json
import signal
import sys

import structlog

logger = structlog.get_logger(__name__)


class SentinelKafkaConsumer:
    """
    Consumes audit events from Kafka and triggers risk scoring.

    Designed to run as a long-lived process via the management command.
    Handles graceful shutdown on SIGTERM/SIGINT.
    """

    def __init__(self, topics: list[str], group_id: str) -> None:
        self.topics = topics
        self.group_id = group_id
        self._running = False
        self._consumer: object = None

    def start(self) -> None:
        """Start consuming. Blocks until shutdown signal received."""
        from django.conf import settings

        try:
            from confluent_kafka import Consumer
        except ImportError:
            logger.error(
                "kafka_consumer_start_failed",
                error="confluent-kafka not installed. Install it: pip install confluent-kafka",
            )
            sys.exit(1)

        self._consumer = Consumer(
            {
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "group.id": self.group_id,
                "client.id": f"sentinel-consumer-{settings.ENVIRONMENT}",
                "auto.offset.reset": "earliest",
                "enable.auto.commit": False,  # Manual commit after processing
                "max.poll.interval.ms": 300_000,  # 5 minutes — long enough for slow risk scoring
                "session.timeout.ms": 45_000,
            }
        )

        self._consumer.subscribe(self.topics)
        self._running = True

        # Graceful shutdown on SIGTERM (Kubernetes pod termination)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

        logger.info(
            "kafka_consumer_started",
            topics=self.topics,
            group_id=self.group_id,
        )

        try:
            while self._running:
                msg = self._consumer.poll(timeout=1.0)

                if msg is None:
                    continue  # No message in this poll window

                if msg.error():
                    from confluent_kafka import KafkaError

                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue  # Reached end of partition — not an error
                    logger.error("kafka_consumer_error", error=str(msg.error()))
                    continue

                self._process_message(msg)

        finally:
            self._consumer.close()
            logger.info("kafka_consumer_stopped")

    def _process_message(self, msg: object) -> None:
        """Process a single Kafka message."""
        try:
            payload = json.loads(msg.value().decode("utf-8"))  # type: ignore[union-attr]
            schema_version = payload.get("schema_version", "unknown")

            if schema_version != "1.0":
                logger.warning(
                    "kafka_unknown_schema",
                    schema_version=schema_version,
                    topic=msg.topic(),  # type: ignore[union-attr]
                )

            event_id = payload.get("id")
            if not event_id:
                logger.error("kafka_message_missing_event_id", payload=str(payload)[:200])
                self._consumer.commit(msg)  # type: ignore[union-attr]
                return

            logger.debug(
                "kafka_message_received",
                event_id=event_id,
                event_type=payload.get("event_type"),
                actor_type=payload.get("actor_type"),
                agent_name=payload.get("agent_name") or None,
            )

            # Trigger risk scoring (synchronous in the consumer — no additional queue)
            from sentinel.risk.services import RiskService

            risk_service = RiskService()
            risk_score = risk_service.process_event(event_id)

            if risk_score:
                # Publish risk score back to Kafka for downstream consumers
                from sentinel.kafka.producer import publish_risk_score

                publish_risk_score(
                    event_id=event_id,
                    risk_score=risk_score.score,
                    risk_level=risk_score.level,
                    tenant_id=payload.get("tenant_id"),
                )

            # Commit offset only after successful processing
            self._consumer.commit(msg)  # type: ignore[union-attr]

        except Exception as exc:
            logger.error(
                "kafka_message_processing_failed",
                topic=getattr(msg, "topic", lambda: "unknown")(),
                error=str(exc),
                exc_info=True,
            )
            # Don't commit — message will be reprocessed on restart

    def _handle_shutdown(self, signum: int, frame: object) -> None:
        """Handle SIGTERM/SIGINT for graceful shutdown."""
        logger.info("kafka_consumer_shutdown_signal", signal=signum)
        self._running = False
