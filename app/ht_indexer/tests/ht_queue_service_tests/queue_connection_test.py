from unittest.mock import Mock, patch

import pytest
from conftest import QueueTestSettings
from ht_queue_service.queue_connection import QueueConnection


@pytest.fixture
def mock_pika_conn() -> Mock:
    return Mock()


class TestQueueConnection:
    """Test the QueueConnection class"""

    def test_real_connect_and_close(self) -> None:
        """Test the connection to RabbitMQ and closing it
        :param get_global_queue_config: Fixture to get the global queue configuration
        :return: None
        """

        rabbit_mq_connection = QueueConnection(QueueTestSettings())

        assert rabbit_mq_connection.queue_connection is not None
        assert rabbit_mq_connection.queue_connection.is_open
        rabbit_mq_connection.close()
        assert rabbit_mq_connection.queue_connection is None

    @patch("pika.ConnectionParameters")
    def test_connect_heartbeat_enabled_passes_nonzero_heartbeat(
        self,
        mock_pika_parameters: Mock,
    ) -> None:
        """Mock pika.BlockingConnection and checks that ConnectionParameters gets heartbeat > 0."""
        # This is expected to fail, we are mocking a critical component
        try:
            QueueConnection(QueueTestSettings(heartbeat=123))
        except Exception:
            pass
        args, kwargs = mock_pika_parameters.call_args
        assert kwargs.get("heartbeat") == 123
