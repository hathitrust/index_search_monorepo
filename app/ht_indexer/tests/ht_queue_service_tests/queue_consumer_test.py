import json
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import pytest
from conftest import close_channel_and_connection, ensure_queue_ready_and_purged
from ht_queue_service.queue_config import QueueConfig
from ht_queue_service.queue_consumer import QueueConsumer
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


@pytest.fixture
def one_message() -> dict[str, Any]:
    """
    This function is used to create a message
    """
    message = {"ht_id": "1234", "ht_title": "Hello World", "ht_author": "John Doe"}
    return message


@pytest.fixture
def list_messages() -> list[dict[str, Any]]:
    """
    This function is used to create a list of messages
    """

    messages: list[dict[str, Any]] = []
    for i in range(10):
        messages.append(
            {"ht_id": f"{i}", "ht_title": f"Hello World {i}", "ht_author": f"John Doe {i}"}
        )
    return messages


class TestQueueConsumer:
    def test_queue_consume_message(
        self, one_message: dict[str, Any], make_queue_config: Callable[..., QueueConfig]
    ) -> None:
        """Test for consuming a message from the queue
        One message is published and consumed, then at the end of the test the queue is empty
        """
        queue_config = make_queue_config(batch_size=1, requeue_message=False)

        producer_instance = QueueProducer(queue_config.queue_params)
        ensure_queue_ready_and_purged(producer_instance)

        # Publish the message to the queue
        producer_instance.publish_messages(one_message)

        logger.info("Closing the producer channel and connection after publishing the message")
        close_channel_and_connection(producer_instance)

        consumer_instance = QueueConsumer(queue_config.queue_params)
        assert consumer_instance.channel is not None

        logger.info(
            f"Starting to consume messages from the queue: "
            f"{consumer_instance.queue_manager.queue_name}"
        )

        for method_frame, _, body in consumer_instance.consume_message(inactivity_timeout=5):
            if method_frame:
                output_message = json.loads(body.decode("utf-8"))

                consumer_instance.positive_acknowledge(
                    consumer_instance.channel, method_frame.delivery_tag
                )
                assert output_message == one_message
                break
            else:
                logger.warning(
                    f"None method_frame in {consumer_instance.queue_manager.queue_name}... Stopping batch consumption."
                )
                break
        consumer_instance.channel.queue_purge(consumer_instance.queue_manager.queue_name)
        logger.info("Closing the channel and connection for the consumer instance")
        close_channel_and_connection(consumer_instance)

    def test_queue_consume_message_empty(
        self, make_queue_config: Callable[..., QueueConfig]
    ) -> None:
        """Test for consuming a message from an empty queue"""
        queue_config = make_queue_config(batch_size=1, requeue_message=False)

        consumer_instance = QueueConsumer(queue_config.queue_params)
        assert consumer_instance.channel is not None

        list_docs: list[dict[str, Any]] = []
        for method_frame, _, body in consumer_instance.consume_message(inactivity_timeout=5):
            assert method_frame is None
            if method_frame:
                output_message = json.loads(body.decode("utf-8"))

                consumer_instance.positive_acknowledge(
                    consumer_instance.channel, method_frame.delivery_tag
                )
                list_docs.append(output_message)
            else:
                logger.warning(
                    f"None method_frame in {consumer_instance.queue_manager.queue_name}... Stopping batch consumption."
                )
                break
        assert list_docs == []
        logger.info("Closing the channel and connection for the consumer instance")
        close_channel_and_connection(consumer_instance)

    def test_queue_requeue_message_requeue_false(
        self, list_messages: list[dict[str, Any]], make_queue_config: Callable[..., QueueConfig]
    ) -> None:
        """Test for re-queueing a message from the queue, the massage with ht_id=5 is rejected and routed
        to the dead letter queue and discarded from the main queue
        """
        producer_queue_config = make_queue_config(batch_size=1, requeue_message=False)

        # Define the producer instance
        producer_instance = QueueProducer(producer_queue_config.queue_params)

        consumer_queue_config = make_queue_config(
            queue_name=producer_queue_config.queue_params.queue_name,
            batch_size=1,
            requeue_message=False,
        )

        # Define the consumer instance
        consumer_instance = QueueConsumer(consumer_queue_config.queue_params)
        ensure_queue_ready_and_purged(consumer_instance)
        assert consumer_instance.channel is not None

        # Create a new channel for the dead letter queue
        dlx_channel = consumer_instance.channel_creator.get_channel()
        assert dlx_channel is not None
        # Clean up the dead letter queue
        dlx_channel.queue_purge(f"{consumer_instance.queue_manager.queue_name}_dlq")

        # Publish the messages to run the test
        for item in list_messages:
            producer_instance.publish_messages(item)

        # Close the producer channel after publishing all messages
        logger.info("Closing the producer channel and connection after publishing all messages")
        close_channel_and_connection(producer_instance)

        # Consume messages from the main queue to reject the message with ht_id=5
        for method_frame, _, body in consumer_instance.consume_message(inactivity_timeout=5):
            if method_frame:
                output_message = json.loads(body.decode("utf-8"))

                # Use the message to raise an exception
                if output_message.get("ht_id") == "5":
                    consumer_instance.reject_message(
                        consumer_instance.channel, method_frame.delivery_tag
                    )
                    logger.info(f"Rejected Message: {output_message}")
                    # time.sleep(1)  # Wait for the message to be routed to the dead letter queue
                else:
                    # Acknowledge the message if the message is processed successfully
                    consumer_instance.positive_acknowledge(
                        consumer_instance.channel, method_frame.delivery_tag
                    )
                logger.info(output_message)
            else:
                logger.info("The queue is empty: Test ended")
                break

        logger.info(f"DLQ NAME: {consumer_instance.queue_manager.queue_name}_dlq")

        # Running the test to consume messages from the dead letter queue
        list_ids = []
        # Consume messages from the dead letter queue
        for method_frame, _, body in consumer_instance.consume_dead_letter_messages(
            dlx_channel,
            inactivity_timeout=5,
            queue_name=f"{consumer_instance.queue_manager.queue_name}_dlq",
        ):
            if method_frame:
                output_message = json.loads(body.decode("utf-8"))
                logger.info(f"Message in dead letter queue: {output_message}")

                list_ids.append(output_message.get("ht_id"))
                consumer_instance.positive_acknowledge(dlx_channel, method_frame.delivery_tag)
            else:
                logger.info("The dead letter queue is empty: Test ended")
                break

        logger.info(f"List of IDs consumed: {list_ids}")
        assert len(list_ids) == 1
        assert "5" in list_ids, "Message with ID '5' was not found in the dead letter queue"

        logger.info(
            f"Deleting all messages in the dead letter queue:"
            f" {consumer_instance.queue_manager.queue_name}_dlq"
        )
        consumer_instance.channel.queue_purge(f"{consumer_instance.queue_manager.queue_name}_dlq")
        # Close the channel
        logger.info(
            f"Closing the channel for the dead letter queue: "
            f"{consumer_instance.queue_manager.queue_name}_dlq"
        )
        dlx_channel.close()

        # Close the consumer channel
        consumer_instance.channel.queue_purge(consumer_instance.queue_manager.queue_name)
        logger.info("Closing the channel and connection for the main queue")
        close_channel_and_connection(consumer_instance)

    def test_queue_requeue_message_requeue_true(
        self, list_messages: list[dict[str, Any]], make_queue_config: Callable[..., QueueConfig]
    ) -> None:
        """Test for re-queueing a message from the queue, the message with ht_id=5 is rejected, and instead of routing the message
        to the dead letter queue, it is requeue to the main queue
        """
        producer_queue_config = make_queue_config(batch_size=1, requeue_message=False)

        # Define the producer instance
        producer_instance = QueueProducer(producer_queue_config.queue_params)
        ensure_queue_ready_and_purged(producer_instance)

        consumer_queue_config = make_queue_config(
            queue_name=producer_queue_config.queue_params.queue_name,
            batch_size=1,
            requeue_message=True,
        )

        # Define the consumer instance
        consumer_instance = QueueConsumer(consumer_queue_config.queue_params)
        assert consumer_instance.channel is not None

        consumer_instance.channel.queue_purge(consumer_instance.queue_manager.queue_name)

        # Publish the messages to run the test
        for item in list_messages[0:6]:  # Only publish the first 5 messages
            producer_instance.publish_messages(item)

        # Close the producer channel after publishing all messages
        logger.info("Closing the producer channel and connection after publishing all messages")
        close_channel_and_connection(producer_instance)

        # Tracks how many times each ht_id is seen
        # Once the message is rejected, it will be requeued to the main queue and RabbitMQ will try to deliver it again,
        # So we will see the message with ht_id=5 multiple times. After 3 redeliveries, the test will stop
        seen_messages: defaultdict[str, int] = defaultdict(int)
        max_redelivery = 3  # maximum allowed redeliveries
        redelivery_count = 0
        for method_frame, _, body in consumer_instance.consume_message(inactivity_timeout=5):
            if method_frame:
                output_message = json.loads(body.decode("utf-8"))
                message_id = output_message.get("ht_id")
                # Increment the seen count
                seen_messages[message_id] += 1

                # For debug/logging
                logger.info(f"Seen ht_id={message_id} count={seen_messages[message_id]}")

                # Use the message to raise an exception
                if message_id == "5":
                    consumer_instance.reject_message(
                        consumer_instance.channel, method_frame.delivery_tag
                    )
                    redelivery_count += 1
                    # time.sleep(1)  # Wait for the message to be routed to the dead letter queue
                    logger.info(f"Rejected Message: {output_message}")
                else:
                    # Acknowledge the message if the message is processed successfully
                    consumer_instance.positive_acknowledge(
                        consumer_instance.channel, method_frame.delivery_tag
                    )
                    # time.sleep(1)  # Wait for the message to be routed to the dead letter queue
                if redelivery_count >= max_redelivery:
                    assert method_frame.redelivered == (
                        message_id == "5"
                    )  # Check if the message is redelivered
                    assert seen_messages[message_id] >= max_redelivery, (
                        f"Message with ht_id={message_id} was redelivered more than {max_redelivery} times"
                    )
                    break
            else:
                logger.info("The queue is empty: Test ended")
                break

        # Now you can assert that a message ht_id=5 has been seen more than once
        assert seen_messages["5"] > 1, "Message with ht_id=5 was not redelivered"

        logger.info(
            f"Queue cleanup: Deleting all messages in the queue: {consumer_instance.queue_manager.queue_name}"
        )
        consumer_instance.channel.queue_purge(consumer_instance.queue_manager.queue_name)
        logger.info("Closing the channel and connection for the main queue")
        close_channel_and_connection(consumer_instance)
