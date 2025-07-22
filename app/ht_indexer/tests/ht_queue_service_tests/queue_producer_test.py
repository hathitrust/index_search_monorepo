import json
import os
from typing import Any

import pytest

from conftest import create_test_queue_config
from ht_queue_service.queue_consumer import QueueConsumer
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

message = {"ht_id": "12345678", "ht_title": "Hello World", "ht_author": "John Doe"}

class TestQueueProducer:
    """Test the QueueProducer class"""

    def test_queue_produce_one_message(self, get_global_queue_config: dict[str, Any],
                                       get_app_queue_config: dict[str, Any]) -> None:
        """Test publishing a single message to the queue and consuming it to verify.
        :param get_global_queue_config: fixture to get the global queue configuration
        :param get_app_queue_config: fixture to get the application queue configuration
        : return: None
        """

        queue_name = "test_queue_produce_one_message"
        batch_size = 1
        requeue_message = False

        producer_queue_config, global_path, app_path = create_test_queue_config(get_global_queue_config,
                                                                                get_app_queue_config,
                                                                                queue_name,
                                                                                batch_size=batch_size,
                                                                                requeue_message=requeue_message)



        producer_instance = QueueProducer(producer_queue_config.queue_params)

        producer_instance.publish_messages(message)
        producer_instance.channel.close()

        # Consume the message to ensure it was published correctly
        consumer_instance = QueueConsumer(producer_queue_config.queue_params)

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

        # Delete the temporary files
        os.remove(global_path)
        os.remove(app_path)

    def test_publish_invalid_message_raises_type_error(self, get_global_queue_config: dict[str, Any],
                                                       get_app_queue_config: dict[str, Any]) -> None:

        """Test non-serializable data - Invalid message format
        :param get_global_queue_config: fixture to get the global queue configuration
        :param get_app_queue_config: fixture to get the application queue configuration
        : return: None
        """

        queue_name = "test_queue_invalid"
        batch_size = 1
        requeue_message = False

        producer_queue_config, global_path, app_path = create_test_queue_config(get_global_queue_config,
                                                                                get_app_queue_config,
                                                                                queue_name,
                                                                                batch_size=batch_size,
                                                                                requeue_message=requeue_message)



        producer_instance = QueueProducer(producer_queue_config.queue_params)

        class NonSerializable:
            pass

        with pytest.raises(TypeError):
            producer_instance.publish_messages({"ht_id": "123", "payload": NonSerializable()})

        # Add close method to ensure the connection is closed after the test
        producer_instance.channel.close()
        producer_instance.channel_creator.connection.queue_connection.close()

        # Delete the temporary files
        os.remove(global_path)
        os.remove(app_path)

    def test_queue_reconnect(self, get_global_queue_config: dict[str, Any], get_app_queue_config: dict[str, Any]) -> None:

        """ Test the queue reconnect functionality of the QueueProducer class
        :param get_global_queue_config: Fixture to get the global queue configuration
        :param get_app_queue_config: Fixture to get the application-specific queue configuration
        :return: None
        """

        queue_name = "test_queue_reconnect"
        batch_size = 1
        requeue_message = False

        producer_queue_config, global_path, app_path = create_test_queue_config(get_global_queue_config,
                                                                                get_app_queue_config,
                                                                                queue_name,
                                                                                batch_size=batch_size,
                                                                                requeue_message=requeue_message)



        producer_instance = QueueProducer(producer_queue_config.queue_params)

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

        # Delete the temporary files
        os.remove(global_path)
        os.remove(app_path)
