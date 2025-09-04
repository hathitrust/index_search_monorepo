import os
from typing import Any

from conftest import create_test_queue_config
from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_manager import QueueManager
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


class TestQueueManager:
    """Test the QueueProducer class"""

    def test_queue_does_not_exist(self, get_global_queue_config: dict[str, Any], get_app_queue_config: dict[str, Any],
                                  get_rabbit_mq_host_name) -> None:
        """Test that the queue does not exist before publishing messages.
        :param get_global_queue_config: fixture to get the global queue configuration
        :param get_app_queue_config: fixture to get the application queue configuration
        : return: None
        """
        queue_name = "test_queue_does_not_exist"

        queue_config, global_path, app_path = create_test_queue_config(get_global_queue_config,
                                                                       get_app_queue_config,
                                                                       queue_name,
                                                                       batch_size=1,
                                                                       requeue_message=False)


        queue_manager = QueueManager(queue_config.queue_params)

        channel_creator = ChannelCreator(user=get_global_queue_config.get("user", "guest"),
                                         password=get_global_queue_config.get("password", "guest"),
                                         host=get_rabbit_mq_host_name)

        # Creating a channel
        channel = channel_creator.get_channel()

        logger.info(f"Test will fail if the queue {queue_name} does not exist before publishing messages")

        result = queue_manager.is_ready(channel)
        assert result is False

        assert channel.is_closed
        channel_creator.connection.queue_connection.close()

        # Cleanup
        os.remove(global_path)
        os.remove(app_path)
