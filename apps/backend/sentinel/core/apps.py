from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "sentinel.core"
    label = "sentinel_core"
    verbose_name = "Sentinel Core"

    def ready(self) -> None:
        """Perform any app initialization that requires the app registry to be loaded."""
        # Import signal handlers when they exist (Phase 2+)
        pass
