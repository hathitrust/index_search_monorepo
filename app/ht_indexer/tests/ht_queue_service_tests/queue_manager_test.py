
from conftest import personalize_queue_config
from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_manager import QueueManager
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class TestQueueManager:
    """Test the QueueProducer class"""

    # TODO: This test does not make sense, because the queue is created in the QueueProducer class.
    # Add this test to the class QueueControllerTest when I implement it.
    def test_queue_does_not_exist(self, get_rabbit_mq_host_name, get_queue_config):
        """Test that the queue does not exist before publishing messages."""
        queue_name = "test_queue_does_not_exist"
        batch_size = 1

        # Create a copy of the queue configuration and update it with the test parameters
        queue_config = personalize_queue_config(get_queue_config, queue_name, batch_size)

        queue_manager = QueueManager(queue_config)

        channel_creator = ChannelCreator(user='guest', password='guest', host=get_rabbit_mq_host_name)

        # Creating a channel
        channel = channel_creator.get_channel()

        logger.info(f"Test will fail if the queue {queue_name} does not exist before publishing messages")

        result = queue_manager.is_ready(channel)
        assert result is False

        assert channel.is_closed
        channel_creator.connection.queue_connection.close()
