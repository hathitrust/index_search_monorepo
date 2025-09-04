import os
from typing import Any

from conftest import create_test_queue_config
from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

class TestChannelCreator:
    """ Test the QueueConnection class """

    def test_create_channel_close(self, get_global_queue_config: dict[str, Any], get_rabbit_mq_host_name) -> None:

        """ Test the creation and closing of a channel using ChannelCreator
        :param get_global_queue_config: Fixture to get the global queue configuration
        :return: None
        """
        channel_creator = ChannelCreator(user=get_global_queue_config.get("user", "guest"),
                                         password=get_global_queue_config.get("password", "guest"),
                                         host=get_rabbit_mq_host_name)

        # Creating a channel
        channel = channel_creator.get_channel()

        assert channel is not None
        assert channel.is_open

        # Closing the channel
        channel.close()
        assert channel.is_closed

    def test_purge_queue(self, get_global_queue_config: dict[str, Any], get_app_queue_config: dict[str, Any]):

        """ Test the purge queue functionality of the QueueProducer class
        :param get_global_queue_config: Fixture to get the global queue configuration
        :param get_app_queue_config: Fixture to get the application-specific queue configuration
        :return: None
        """

        queue_name = "test_purge_queue"

        queue_config, global_path, app_path = create_test_queue_config(get_global_queue_config, get_app_queue_config,
                                                                       queue_name,
                                                                       batch_size=1,
                                                                       requeue_message=False)

        # Create producer instance
        queue_producer = QueueProducer(queue_config.queue_params)

        if not queue_producer.queue_manager.is_ready(queue_producer.channel):
            # The channel will be closed if the queue doesn't exist or is declared with different options.
            # is_ready() method will return False and will create a new channel.
            queue_producer.queue_reconnect()
            # queue_producer.queue_setup.set_up_queue()

        assert queue_producer.channel.is_open

        # Purge the queue before the test
        queue_producer.channel.queue_purge(queue_name)
        logger.info(f'Queue purged before publishing messages in the queue {queue_name}.')

        # Test logic here
        queue_producer.publish_messages({"ht_id": 3, "content": "Content of the message"})

        # Purge the queue after the test
        queue_producer.channel.queue_purge(queue_name)
        # Use passive=True to avoid creating a queue if it doesn't exist
        status = queue_producer.channel.queue_declare(queue=queue_name, durable=True, passive=True)
        assert status.method.message_count == 0

        queue_producer.channel.close()
        queue_producer.channel_creator.connection.queue_connection.close()

        # Cleanup
        os.remove(global_path)
        os.remove(app_path)