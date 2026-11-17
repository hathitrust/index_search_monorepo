from conftest import QueueTestSettings
from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_manager import QueueManager
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class TestQueueManager:
    """Test the QueueProducer class"""

    def test_queue_does_not_exist(
        self,
    ) -> None:
        """Test that the queue does not exist before publishing messages.
        : return: None
        """

        queue_name = "test_queue_does_not_exist"

        settings = QueueTestSettings(queue_name=queue_name)

        queue_manager = QueueManager(settings)

        channel_creator = ChannelCreator(settings)
        # Creating a channel
        channel = channel_creator.get_channel()

        logger.info(
            f"Test will fail if the queue {queue_name} does not exist before publishing messages"
        )

        result = queue_manager.is_ready(channel)
        assert result is False

        assert channel is not None
        assert channel.is_closed
        assert channel_creator.connection.queue_connection is not None
        channel_creator.connection.queue_connection.close()
