import copy

from conftest import create_queue_config_attributes
from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger
from ht_utils.ht_utils import update_dict_fields

logger = get_ht_logger(name=__name__)

class TestChannelFactory:
    """ Test the QueueConnection class """

    def test_create_channel_close(self, rabbit_mq_connection, get_rabbit_mq_host_name):

        channel_creator = ChannelCreator(user='guest', password='guest', host=get_rabbit_mq_host_name)

        # Creating a channel
        channel = channel_creator.get_channel()

        assert channel is not None
        assert channel.is_open

        # Closing the channel
        channel.close()
        assert channel.is_closed

    def test_purge_queue(self, get_rabbit_mq_host_name, get_queue_config):

        queue_name = "test_purge_queue"
        batch_size = 1

        # Create a copy of the queue configuration and update it with the test parameters
        # This ensures that the original configuration remains unchanged.
        copy_queue_config = copy.deepcopy(get_queue_config)
        test_parameters = create_queue_config_attributes(get_queue_config, queue_name, batch_size)
        update_dict_fields(copy_queue_config, list(test_parameters.keys()), list(test_parameters.values()))

        # Create producer instance
        queue_producer = QueueProducer("guest", "guest", get_rabbit_mq_host_name, copy_queue_config)

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