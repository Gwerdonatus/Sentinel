"""
Sentinel Kafka Producer.

Publishes audit events to tenant-scoped Kafka topics after they are
written to PostgreSQL. Kafka provides the durable, ordered, replayable
event stream that downstream consumers (risk engine, webhooks, external
integrations) subscribe to.

TOPIC NAMING:
    sentinel.{tenant_id}.audit.events   — all ingested audit events
    sentinel.{tenant_id}.risk.scores    — scored events from risk engine
    sentinel.{tenant_id}.alerts         — fired alerts

WHY KAFKA AFTER POSTGRES (not instead of):
    PostgreSQL is the source of truth. Kafka is the distribution layer.
    We write to Postgres first, then publish to Kafka. If Kafka is down,
    events are still recorded and the backlog can be replayed once it
    recovers. If Postgres is down, nothing is lost to Kafka either.

    This is the "transactional outbox" pattern without a dedicated
    outbox table — acceptable at Phase 5 scale. A true transactional
    outbox (Debezium CDC) would be Phase 6+.

SERIALIZATION:
    Events are serialized to JSON. The schema is versioned via a
    "schema_version" field in every message so consumers can handle
    schema evolution gracefully.

CONFIGURATION:
    All Kafka settings come from environment variables with KAFKA_ prefix.
    Producer is a process-level singleton — one connection per Django worker.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sentinel.audit.models import AuditEvent

logger = structlog.get_logger(__name__)

_producer: "KafkaProducer | None" = None  # type: ignore[name-defined]


def get_producer() -> "KafkaProducer":  # type: ignore[name-defined]
    """
    Return the process-level Kafka producer singleton.
    Created lazily on first use, reused across requests.
    """
    global _producer

    if _producer is None:
        from django.conf import settings

        try:
            from confluent_kafka import Producer

            _producer = Producer({
                "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                "client.id": f"sentinel-backend-{settings.ENVIRONMENT}",
                "acks": "all",                    # Wait for all replicas to ack
                "retries": 5,
                "retry.backoff.ms": 100,
                "compression.type": "snappy",
                "linger.ms": 5,                   # Batch messages for 5ms
                "batch.size": 32768,               # 32KB batches
                "enable.idempotence": True,        # Exactly-once delivery semantics
            })
            logger.info("kafka_producer_initialized", servers=settings.KAFKA_BOOTSTRAP_SERVERS)
        except ImportError:
            logger.warning(
                "kafka_not_available",
                message="confluent-kafka not installed. Events will not be published to Kafka.",
            )
            _producer = _NoOpProducer()  # type: ignore[assignment]

    return _producer  # type: ignore[return-value]


def publish_audit_event(event: "AuditEvent") -> None:
    """
    Publish a recorded AuditEvent to its tenant's Kafka topic.

    Called from record_audit_event_task after successful DB write.
    Failures are logged but do not raise — Kafka unavailability must
    not prevent audit events from being recorded in PostgreSQL.
    """
    try:
        producer = get_producer()
        topic = _get_topic_for_event(event)
        payload = _serialize_audit_event(event)

        producer.produce(
            topic=topic,
            key=str(event.id).encode(),
            value=json.dumps(payload).encode(),
            callback=_delivery_callback,
        )
        producer.poll(0)  # Trigger delivery callbacks without blocking

        logger.debug(
            "kafka_event_published",
            event_id=str(event.id),
            event_type=event.event_type,
            topic=topic,
        )

    except Exception as exc:
        # Never raise — Kafka failure must not break the audit pipeline
        logger.error(
            "kafka_publish_failed",
            event_id=str(event.id),
            event_type=event.event_type,
            error=str(exc),
        )


def publish_risk_score(event_id: str, risk_score: int, risk_level: str, tenant_id: str | None) -> None:
    """Publish a computed risk score to the risk scores topic."""
    try:
        producer = get_producer()
        topic = _get_topic(tenant_id, "risk.scores")

        payload = {
            "schema_version": "1.0",
            "event_id": event_id,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "computed_at": datetime.utcnow().isoformat() + "Z",
        }

        producer.produce(
            topic=topic,
            key=event_id.encode(),
            value=json.dumps(payload).encode(),
            callback=_delivery_callback,
        )
        producer.poll(0)

    except Exception as exc:
        logger.error("kafka_risk_score_publish_failed", event_id=event_id, error=str(exc))


def publish_alert(alert_id: str, rule_name: str, severity: str, tenant_id: str | None) -> None:
    """Publish a fired alert to the alerts topic."""
    try:
        producer = get_producer()
        topic = _get_topic(tenant_id, "alerts")

        payload = {
            "schema_version": "1.0",
            "alert_id": alert_id,
            "rule_name": rule_name,
            "severity": severity,
            "fired_at": datetime.utcnow().isoformat() + "Z",
        }

        producer.produce(
            topic=topic,
            key=alert_id.encode(),
            value=json.dumps(payload).encode(),
            callback=_delivery_callback,
        )
        producer.poll(0)

    except Exception as exc:
        logger.error("kafka_alert_publish_failed", alert_id=alert_id, error=str(exc))


# =============================================================================
# Private helpers
# =============================================================================

def _get_topic_for_event(event: "AuditEvent") -> str:
    tenant_id = getattr(event, "tenant_id", None)
    return _get_topic(str(tenant_id) if tenant_id else None, "audit.events")


def _get_topic(tenant_id: str | None, topic_type: str) -> str:
    from django.conf import settings
    if tenant_id:
        return f"sentinel.{tenant_id}.{topic_type}"
    # Single-tenant or platform-level events use the default topic
    return f"sentinel.default.{topic_type}"


def _serialize_audit_event(event: "AuditEvent") -> dict[str, object]:
    """Serialize an AuditEvent to the Kafka message schema v1.0."""
    return {
        "schema_version": "1.0",
        "id": str(event.id),
        "tenant_id": str(event.tenant_id) if getattr(event, "tenant_id", None) else None,
        "event_type": event.event_type,
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "actor_type": getattr(event, "actor_type", "HUMAN"),
        "actor_email": event.actor_email,
        "actor_role": event.actor_role,
        "actor_ip": event.actor_ip,
        "agent_name": getattr(event, "agent_name", ""),
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "metadata": event.metadata,
        "request_id": event.request_id,
        "signature": event.signature,
        "risk_score": getattr(event, "risk_score", None),
        "created_at": event.created_at.isoformat(),
    }


def _delivery_callback(err: object, msg: object) -> None:
    """Kafka delivery confirmation callback."""
    if err:
        logger.error(
            "kafka_delivery_failed",
            topic=getattr(msg, "topic", lambda: "unknown")(),
            error=str(err),
        )


class _NoOpProducer:
    """
    Fallback producer when confluent-kafka is not installed.
    Allows the application to run without Kafka in development.
    """

    def produce(self, *args: object, **kwargs: object) -> None:
        pass

    def poll(self, *args: object, **kwargs: object) -> None:
        pass

    def flush(self, *args: object, **kwargs: object) -> None:
        pass
