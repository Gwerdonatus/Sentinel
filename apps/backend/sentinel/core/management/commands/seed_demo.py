"""Create deterministic, explicitly synthetic data for the local Sentinel demo."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from sentinel.api_keys.models import ActorType as APIKeyActorType
from sentinel.api_keys.models import APIKey
from sentinel.api_keys.services import APIKeyService
from sentinel.audit.models import ActorType, AuditEvent
from sentinel.audit.services import AuditEventService
from sentinel.risk.services import RiskService


class Command(BaseCommand):
    help = "Seed an idempotent synthetic dataset for local screen recordings."

    def handle(self, *args: object, **options: object) -> None:
        if settings.ENVIRONMENT == "production":
            raise CommandError("seed_demo is disabled in production")

        User = get_user_model()
        admin, _ = User.objects.get_or_create(
            email="demo.admin@sentinel.local",
            defaults={"role": "ADMIN", "is_staff": True, "is_superuser": True},
        )
        admin.role = "ADMIN"
        admin.is_staff = True
        admin.is_superuser = True
        admin.set_password("SentinelDemo123!")
        admin.save()

        key_service = APIKeyService()
        key = APIKey.objects.filter(
            name="Demo Reconciliation Agent",
            deleted_at__isnull=True,
        ).first()
        if key:
            key, full_key = key_service.rotate(str(key.id), requesting_user=admin)
        else:
            key, full_key = key_service.create(
                name="Demo Reconciliation Agent",
                actor_type=APIKeyActorType.AI_AGENT,
                scopes=["events:write"],
                created_by=admin,
                environment="test",
                agent_name="reconciliation-agent",
                agent_version="v1.0",
                agent_description="Synthetic agent used for the local Sentinel walkthrough.",
            )

        service = AuditEventService()
        now = timezone.now()
        for index in range(8):
            request_id = f"demo-baseline-{index}"
            if AuditEvent.objects.filter(request_id=request_id).exists():
                continue
            service.record(
                event_type="ADMIN_ACTION",
                actor_id=str(key.id),
                actor_type=ActorType.AI_AGENT,
                actor_role="API_KEY",
                actor_ip="127.0.0.1",
                agent_name=key.agent_name,
                resource_type="support_ticket",
                resource_id=f"ticket-{1000 + index}",
                metadata={"demo_data": True, "action": "read"},
                request_id=request_id,
                created_at=now - timedelta(days=8 - index),
            )

        suspicious_request_id = "demo-suspicious-transfer"
        suspicious = AuditEvent.objects.filter(request_id=suspicious_request_id).first()
        if suspicious is None:
            suspicious = service.record(
                event_type="TRANSFER_INITIATED",
                actor_id=str(key.id),
                actor_type=ActorType.AI_AGENT,
                actor_role="API_KEY",
                actor_ip="127.0.0.1",
                agent_name=key.agent_name,
                resource_type="transfer",
                resource_id="demo-transfer-9001",
                metadata={
                    "demo_data": True,
                    "amount": "25000.00",
                    "currency": "USD",
                    "explanation": "Synthetic out-of-pattern resource access",
                },
                request_id=suspicious_request_id,
            )

        RiskService().process_event(str(suspicious.id))

        self.stdout.write(self.style.SUCCESS("Synthetic Sentinel demo data is ready."))
        self.stdout.write("Dashboard: http://localhost:3000")
        self.stdout.write("Login: demo.admin@sentinel.local")
        self.stdout.write("Password: SentinelDemo123!")
        self.stdout.write(f"Rotated demo API key (shown once): {full_key}")
        self.stdout.write("All generated audit events contain metadata.demo_data=true.")
