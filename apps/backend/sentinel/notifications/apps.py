from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "sentinel.notifications"
    label = "sentinel_notifications"
    verbose_name = "Sentinel Notifications"

    def ready(self) -> None:
        pass
