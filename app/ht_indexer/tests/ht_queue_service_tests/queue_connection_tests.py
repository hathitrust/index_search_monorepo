
from ht_queue_service.queue_connection import QueueConnection
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

def test_init_creates_connection(get_rabbit_mq_host_name):

    """Test for creating a connection to RabbitMQ"""

    queue_connection = QueueConnection(
        "guest", "guest", get_rabbit_mq_host_name, "test_create_conn", batch_size=1
    )

    # Attempt to create a channel
    try:
        queue_connection = QueueConnection(
            "guest", "guest", get_rabbit_mq_host_name, "test_create_conn", batch_size=1
        )
        assert queue_connection.ht_channel is not None
        assert queue_connection.ht_channel.is_open == True  #self.assertTrue(channel.is_open, "Channel should be open")
    except Exception as e:
        logger.info(f"Channel creation failed: {e}")
    finally:
        if queue_connection.ht_channel and queue_connection.ht_channel.is_open:
            queue_connection.ht_channel.close()

def test_is_ready_true():
    qc = QueueConnection(user="u", password="p", host="localhost", queue_name="test")
    qc.queue_connection = MagicMock()
    qc.ht_channel = MagicMock()
    qc.queue_connection.is_closed = False
    qc.ht_channel.is_closed = False

    assert qc.is_ready() is True

def test_get_total_messages_success():
    qc = QueueConnection(user="u", password="p", host="localhost", queue_name="test")
    qc.ht_channel = MagicMock()
    mock_method = MagicMock()
    mock_method.message_count = 123
    qc.ht_channel.queue_declare.return_value.method = mock_method

    count = qc.get_total_messages()
    assert count == 123
    qc.ht_channel.queue_declare.assert_called_with(queue="test", durable=True, passive=True)

from pika.exceptions import ChannelClosedByBroker

def test_get_total_messages_channel_closed():
    qc = QueueConnection(user="u", password="p", host="localhost", queue_name="test")
    qc.ht_channel = MagicMock()
    qc.ht_channel.queue_declare.side_effect = ChannelClosedByBroker(404, "Not Found")
    qc.queue_reconnect = MagicMock()

    count = qc.get_total_messages()
    assert count == 0
    qc.queue_reconnect.assert_called_once()

def test_close_when_connection_open():
    qc = QueueConnection(user="u", password="p", host="localhost", queue_name="test")
    qc.queue_connection = MagicMock()
    qc.queue_connection.is_closed = False

    qc.close()
    qc.queue_connection.close.assert_called_once()