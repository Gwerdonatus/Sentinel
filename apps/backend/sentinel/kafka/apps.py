from django.apps import AppConfig


class KafkaConfig(AppConfig):
    name = "sentinel.kafka"
    label = "sentinel_kafka"
    verbose_name = "Sentinel Kafka Integration"

    def ready(self) -> None:
        pass
