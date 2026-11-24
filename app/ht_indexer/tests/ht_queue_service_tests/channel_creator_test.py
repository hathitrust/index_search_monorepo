from conftest import QueueTestSettings
from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class TestChannelCreator:
    """Test the QueueConnection class"""

    def test_create_channel_close(self) -> None:
        """Test the creation and closing of a channel using ChannelCreator
        :return: None
        """

        channel_creator = ChannelCreator(QueueTestSettings())

        # Creating a channel
        channel = channel_creator.get_channel()

        assert channel is not None
        assert channel.is_open

        # Closing the channel
        channel.close()
        assert channel.is_closed

    def test_purge_queue(self) -> None:
        """Test the purge queue functionality of the QueueProducer class
        :return: None
        """

        queue_name = "test_purge_queue"
        queue_settings = QueueTestSettings(queue_name=queue_name)

        # Create producer instance
        queue_producer = QueueProducer(queue_settings)

        assert queue_producer.channel is not None
        assert queue_producer.channel.is_open

        # Purge the queue before the test
        queue_producer.channel.queue_purge(queue_name)
        logger.info(f"Queue purged before publishing messages in the queue {queue_name}.")

        # Test logic here
        queue_producer.publish_messages({"ht_id": 3, "content": "Content of the message"})

        # Purge the queue after the test
        queue_producer.channel.queue_purge(queue_name)
        # Use passive=True to avoid creating a queue if it doesn't exist
        status = queue_producer.channel.queue_declare(queue=queue_name, durable=True, passive=True)
        assert status.method.message_count == 0

        queue_producer.channel.close()
        assert queue_producer.channel_creator.connection.queue_connection is not None
        queue_producer.channel_creator.connection.queue_connection.close()
