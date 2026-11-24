import pytest

from unittest.mock import Mock, patch
from pika.exceptions import AMQPConnectionError, ProbableAuthenticationError

from ht_utils.ht_errors import HTError
from conftest import QueueTestSettings, queue_settings
from ht_queue_service.queue_connection import QueueConnection
from ht_utils.testing import assert_log_entry, capture_logs


@pytest.fixture
def mock_pika_conn() -> Mock:
    return Mock()

class TestQueueConnection:
    """Test the QueueConnection class"""

    def test_connect_builds_pika_connection(self) -> None:
        """Test that the QueueConnection class builds a pika connection with the correct parameters"""
        with (
            patch("pika.Connection") as mock_pika_connection,
            patch("pika.ConnectionParameters") as mock_pika_parameters,
        ):
            queue_connection = QueueConnection(QueueTestSettings())
            mock_pika_connection.assert_called_once_with(mock_pika_parameters.return_value)
            assert queue_connection.queue_connection is mock_pika_connection.return_value

    @pytest.mark.parametrize(
        ("error", "message"),
        [
            pytest.param(
                AMQPConnectionError("connection failed"),
                "Could not connect to RabbitMQ at {host}. Please check your connection settings.",
                id="amqp-connection-error",
            ),
            pytest.param(
                ProbableAuthenticationError("authentication failed"),
                "Could not connect to RabbitMQ at {host}. Please check your connection settings.",
                id="authentication-error",
            ),
            pytest.param(
                RuntimeError("unexpected failure"),
                "Could not connect to RabbitMQ at {host}.",
                id="unexpected-error",
            ),
        ],
    )
    def test_connect_error_raises_ht_error(self, error: Exception, message: str, queue_settings: QueueTestSettings) -> None:

        with patch("pika.Connection", side_effect=error), pytest.raises(HTError) as exc_info:
            QueueConnection(queue_settings)

        assert str(exc_info.value) == message.format(host=queue_settings.host)
        assert exc_info.value.__cause__ is error

    @pytest.mark.integration
    def test_channel_create_and_close_returns_open_channel(self) -> None:
        """Test the creation and closing of a channel from the QueueConnection class
        :return: None
        """

        queue_connection = QueueConnection(QueueTestSettings())
        
        # Create a channel from the connection
        try:
            channel = queue_connection.channel()
        
            assert channel is not None
            assert channel.is_open
            
            channel.close()
            assert channel.is_closed
        finally:
            queue_connection.close()

    def test_channel_closed_connection_returns_none(self) -> None:
        settings = QueueTestSettings(
            rabbitmq_ht_indexer_host="rabbitmq.test",
            rabbitmq_ht_indexer_username="test",
            rabbitmq_ht_indexer_password="test",
        )

        with patch("pika.Connection") as mock_connection, capture_logs() as logs:
            mock_connection.return_value.is_closed = True
            connection = QueueConnection(settings)

            channel = connection.channel()

        assert channel is None
        mock_connection.return_value.channel.assert_not_called()
        assert_log_entry(
            logs,
            event="RabbitMQ connection is not established or is closed.",
            level="error",
        )

    def test_channel_pika_error_raises_runtime_error(self, queue_settings) -> None:

        error = AMQPConnectionError("channel failed")

        with patch("pika.Connection") as mock_connection:
            mock_connection.return_value.is_closed = False
            mock_connection.return_value.channel.side_effect = error
            connection = QueueConnection(queue_settings)

            with pytest.raises(RuntimeError) as exc_info:
                connection.channel()

        assert str(exc_info.value) == "Failed to create channel: channel failed"
        assert exc_info.value.__cause__ is error

    @pytest.mark.parametrize(
        ("case", "close_calls", "success_logs"),
        [
            pytest.param("close-twice", 1, 1, id="close-twice"),
            pytest.param("already-closed", 0, 0, id="connection-already-closed"),
            pytest.param("close-raises", 1, 0, id="close-raises"),
        ],
    )
    def test_close_is_safe_when_already_closed(
        self,
        queue_settings: QueueTestSettings,
        case: str,
        close_calls: int,
        success_logs: int,
    ) -> None:
        with patch("pika.Connection") as mock_connection, capture_logs() as logs:
            pika_connection = mock_connection.return_value
            pika_connection.is_closed = case == "already-closed"
            if case == "close-raises":
                pika_connection.close.side_effect = RuntimeError("close failed")

            connection = QueueConnection(queue_settings)

            connection.close()
            connection.close()

        assert connection.queue_connection is None
        assert pika_connection.close.call_count == close_calls
        assert (
            sum(entry["event"] == "RabbitMQ connection closed." for entry in logs) == success_logs
        )
        if case == "close-raises":
            assert_log_entry(
                logs, event="Error closing RabbitMQ connection: close failed", level="warning"
            )

    def test_real_connect_and_close(self) -> None:
        """Test the connection to RabbitMQ and closing it

        :return: None
        """

        rabbit_mq_connection = QueueConnection(QueueTestSettings())

        assert rabbit_mq_connection.queue_connection is not None
        assert rabbit_mq_connection.queue_connection.is_open
        rabbit_mq_connection.close()
        assert rabbit_mq_connection.queue_connection is None



    @patch("pika.ConnectionParameters")
    @pytest.mark.parametrize("heartbeat", [123], ids=["custom-heartbeat"])
    def test_connect_heartbeat_enabled_passes_nonzero_heartbeat(
        self,
        mock_pika_parameters: Mock,
        heartbeat: int,
    ) -> None:
        """Mock pika.BlockingConnection and checks that ConnectionParameters gets heartbeat > 0."""
        # This is expected to fail, we are mocking a critical component
        try:
            QueueConnection(QueueTestSettings(heartbeat=heartbeat))
        except Exception:
            pass
        args, kwargs = mock_pika_parameters.call_args
        assert kwargs.get("heartbeat") == heartbeat
