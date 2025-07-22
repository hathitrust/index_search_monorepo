import copy
import json

import pytest
from conftest import personalize_queue_config
from ht_queue_service.queue_consumer import QueueConsumer
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

message = {"ht_id": "12345678", "ht_title": "Hello World", "ht_author": "John Doe"}

class TestQueueProducer:
    """Test the QueueProducer class"""

    def test_queue_produce_one_message(self, get_rabbit_mq_host_name, get_queue_config):

        queue_name = "test_queue_produce_one_message"
        batch_size = 1
        requeue_message = False

        query_config_dict = personalize_queue_config(get_queue_config, queue_name, batch_size)

        producer_instance = QueueProducer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            query_config_dict
        )

        producer_instance.publish_messages(message)
        producer_instance.channel.close()

        consumer_query_config_dict = copy.deepcopy(query_config_dict)
        consumer_query_config_dict.update({"requeue_message": requeue_message})
        # Consume the message to ensure it was published correctly
        consumer_instance = QueueConsumer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            consumer_query_config_dict
        )

        list_message = []
        for method_frame, _ , body in consumer_instance.consume_message(inactivity_timeout=5):

            if method_frame:
                output_message = json.loads(body.decode('utf-8'))
                list_message.append(output_message)
                consumer_instance.positive_acknowledge(consumer_instance.channel, method_frame.delivery_tag)
                assert len(list_message) == 1
                break
            else:
                logger.warning(f"None method_frame in {consumer_instance.queue_manager.queue_name}... Stopping batch consumption.")
                break

    def test_publish_invalid_message_raises_type_error(self, get_rabbit_mq_host_name, get_queue_config):

        """Test non-serializable data - Invalid message format"""

        queue_name = "test_queue_invalid"
        batch_size = 1
        producer_config_dict = personalize_queue_config(get_queue_config, queue_name, batch_size)

        producer_instance = QueueProducer("guest",
                                          "guest",
                                          get_rabbit_mq_host_name,
                                          producer_config_dict
                                          )

        class NonSerializable:
            pass

        with pytest.raises(TypeError):
            producer_instance.publish_messages({"ht_id": "123", "payload": NonSerializable()})

        # Add close method to ensure the connection is closed after the test
        producer_instance.channel.close()
        producer_instance.channel_creator.connection.queue_connection.close()

    def test_queue_reconnect(self, get_rabbit_mq_host_name, get_queue_config):

        queue_name = "test_queue_reconnect"
        batch_size = 1

        producer_config_dict = personalize_queue_config(get_queue_config, queue_name, batch_size)

        producer_instance = QueueProducer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            producer_config_dict
        )

        # Check if the connection is open
        assert producer_instance.channel_creator.connection.queue_connection.is_open
        assert producer_instance.channel.is_open


        # Close the channel
        producer_instance.channel.close()

        assert producer_instance.channel.is_closed

        producer_instance.queue_reconnect()

        assert producer_instance.channel.is_open

        # Close channel and connection after the test
        producer_instance.channel.close()
        producer_instance.channel_creator.connection.queue_connection.close()
