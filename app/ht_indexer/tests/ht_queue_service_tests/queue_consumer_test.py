import json
import pytest

from collections import defaultdict

from ht_queue_service.channel_creator import ChannelCreator
from ht_queue_service.queue_consumer import QueueConsumer
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

@pytest.fixture
def one_message():
    """
    This function is used to create a message
    """
    message = {"ht_id": "1234", "ht_title": "Hello World", "ht_author": "John Doe"}
    return message


@pytest.fixture
def list_messages():
    """
    This function is used to create a list of messages
    """

    messages = []
    for i in range(10):
        messages.append({"ht_id": f"{i}", "ht_title": f"Hello World {i}", "ht_author": f"John Doe {i}"})
    return messages

class QueueConsumer:

    def queue_consume_message(self, one_message, get_rabbit_mq_host_name):
        """ Test for consuming a message from the queue
        One message is published and consumed, then at the end of the test the queue is empty
        """

        producer_instance = QueueProducer(
            user= "guest", password="guest", host=get_rabbit_mq_host_name,
            queue_name="test_queue_consume_message", batch_size=1,
            exchange_name="ht_exchange"
        )
        # Create the channel
        producer_channel_factory = ChannelCreator(producer_instance)
        producer_channel = producer_channel_factory.get_channel()

        # Publish the message
        producer_instance.publish_messages(one_message, producer_channel)

        producer_channel_factory.close_channel()
        producer_instance.close()

        consumer_instance = QueueConsumer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            "test_queue_consume_message",
            requeue_message=False,
            batch_size=1,
            exchange_name="ht_exchange"
        )

        # Create the channel
        consumer_channel_factory = ChannelCreator(consumer_instance)
        consumer_channel = consumer_channel_factory.get_channel()

        # Clean up the queue
        if consumer_instance.queue_setup:
            consumer_channel.queue_purge(consumer_instance.queue_name)

        for method_frame, properties, body in consumer_instance.consume_message(consumer_channel,
                                                                                inactivity_timeout=5):

            if method_frame:
                output_message = json.loads(body.decode('utf-8'))

                consumer_instance.positive_acknowledge(consumer_channel, method_frame.delivery_tag)
                assert output_message == one_message
                break
            else:
                logger.warning(f"None method_frame in {consumer_instance.queue_name}... Stopping batch consumption.")
                break
        if consumer_instance.queue_setup:
            consumer_channel.queue_purge(consumer_instance.queue_name)

        # Close the channels
        consumer_channel_factory.close_channel()
        # Close the TCP connection
        consumer_instance.close()

    def queue_consume_message_empty(self, get_rabbit_mq_host_name):
        """ Test for consuming a message from an empty queue"""

        consumer_instance = QueueConsumer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            "test_queue_consume_message_empty",
            False,
            1,
            exchange_name="ht_exchange"
        )

        # Create the channel
        channel_factory = ChannelCreator(consumer_instance)
        consumer_channel = channel_factory.get_channel()

        if consumer_instance.queue_setup:
            # Clean up the queue
            consumer_channel.queue_purge(consumer_instance.queue_name)

        list_docs = []
        for method_frame, properties, body in consumer_instance.consume_message(consumer_channel,
                                                                                inactivity_timeout=5):

            assert method_frame is None
            if method_frame:
                output_message = json.loads(body.decode('utf-8'))

                consumer_instance.positive_acknowledge(consumer_channel, method_frame.delivery_tag)
                list_docs.append(output_message)
            else:
                logger.warning(f"None method_frame in {consumer_instance.queue_name}... Stopping batch consumption.")
                break
        assert list_docs == []

    def queue_requeue_message_requeue_false(self, list_messages, get_rabbit_mq_host_name):
        """ Test for re-queueing a message from the queue, the massage with ht_id=5 is rejected and routed
        to the dead letter queue and discarded from the main queue"""

        # Define the producer instance
        producer_instance = QueueProducer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            "test_queue_requeue_message_requeue_false",
            batch_size=1,
            exchange_name="ht_exchange"
        )
        # Create the producer channel
        producer_channel_factory = ChannelCreator(producer_instance)
        producer_channel = producer_channel_factory.get_channel()

        # Publish the messages to run the test
        for item in list_messages:
            producer_instance.publish_messages(item, producer_channel)

        producer_channel_factory.close_channel()

        # Define the consumer instance
        consumer_instance = QueueConsumer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            "test_queue_requeue_message_requeue_false",
            False,
            1,
            exchange_name="ht_exchange"
        )
        # Create the channel
        consumer_channel_factory = ChannelCreator(consumer_instance)
        consumer_channel = consumer_channel_factory.get_channel()

        # Clean up the queue
        if consumer_instance.queue_setup:
            consumer_channel.queue_purge(consumer_instance.queue_name)


        # Create a new channel for the dead letter queue
        dlx_channel = consumer_channel_factory.get_channel()
        # Clean up the dead letter queue
        dlx_channel.queue_purge(f"{consumer_instance.queue_name}_dlq")

        # Consume messages from the main queue to reject the message with ht_id=5
        for method_frame, properties, body in consumer_instance.consume_message(consumer_channel,
            inactivity_timeout=5
        ):
            if method_frame:
                output_message = json.loads(body.decode("utf-8"))

                # Use the message to raise an exception
                if output_message.get("ht_id") == "5":
                    consumer_instance.reject_message(
                        consumer_channel, method_frame.delivery_tag
                    )
                    logger.info(f"Rejected Message: {output_message}")
                    #time.sleep(1)  # Wait for the message to be routed to the dead letter queue
                else:
                    # Acknowledge the message if the message is processed successfully
                    consumer_instance.positive_acknowledge(
                            consumer_channel, method_frame.delivery_tag
                        )
                logger.info(output_message)
            else:
                logger.info("The queue is empty: Test ended")
                break

        logger.info(f"DLQ NAME: {consumer_instance.queue_name}_dlq")

        # Running the test to consume messages from the dead letter queue
        list_ids = []
        # Consume messages from the dead letter queue
        for method_frame, properties, body in consumer_instance.consume_dead_letter_messages(dlx_channel,
                                                                inactivity_timeout=5,
                                                queue_name=f"{consumer_instance.queue_name}_dlq"):
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

        consumer_channel_factory.close_channel()  # Close the consumer channel
        #consumer_channel.queue_purge(consumer_instance.queue_name)

    def queue_requeue_message_requeue_true(self, get_rabbit_mq_host_name, list_messages):
        """ Test for re-queueing a message from the queue, the message with ht_id=5 is rejected, and instead of routing the message
        to the dead letter queue, it is requeue to the main queue"""

        # Define the producer instance
        producer_instance = QueueProducer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            "test_queue_requeue_message_requeue_true",
            batch_size=1,
            exchange_name="ht_exchange"
        )

        # Create the channel
        producer_channel_factory = ChannelCreator(producer_instance)
        producer_channel = producer_channel_factory.get_channel()

        # Clean up the queue
        if producer_instance.queue_setup:
            producer_channel.queue_purge(producer_instance.queue_name)

        # Publish the messages to run the test
        for item in list_messages[0:6]:  # Only publish the first 5 messages
            producer_instance.publish_messages(item, producer_channel)

        producer_channel_factory.close_channel()

        # Define the consumer instance
        consumer_instance = QueueConsumer(
            "guest",
            "guest",
            get_rabbit_mq_host_name,
            "test_queue_requeue_message_requeue_true",
            True,
            1,
            exchange_name="ht_exchange"
        )

        # Create the channel
        consumer_channel_factory = ChannelCreator(consumer_instance)
        consumer_channel = consumer_channel_factory.get_channel()

        # Clean up the queue
        if consumer_instance.queue_setup:
            consumer_channel.queue_purge(consumer_instance.queue_name)

        # Tracks how many times each ht_id is seen
        # Once the message is rejected, it will be requeued to the main queue and RabbitMQ will try to deliver it again,
        # So we will see the message with ht_id=5 multiple times. After 3 redeliveries, the test will stop
        seen_messages = defaultdict(int)
        max_redelivery = 3  # maximum allowed redeliveries
        redelivery_count = 0
        for method_frame, properties, body in consumer_instance.consume_message(consumer_channel, inactivity_timeout=5):

            if method_frame:
                output_message = json.loads(body.decode("utf-8"))
                message_id = output_message.get("ht_id")
                # Increment the seen count
                seen_messages[message_id] += 1

                # For debug/logging
                logger.info(f'Seen ht_id={message_id} count={seen_messages[message_id]}')

                # Use the message to raise an exception
                if message_id == "5":
                    consumer_instance.reject_message(consumer_channel, method_frame.delivery_tag)
                    redelivery_count += 1
                    #time.sleep(1)  # Wait for the message to be routed to the dead letter queue
                    logger.info(f"Rejected Message: {output_message}")
                else:
                    # Acknowledge the message if the message is processed successfully
                    consumer_instance.positive_acknowledge(consumer_channel, method_frame.delivery_tag)
                    #time.sleep(1)  # Wait for the message to be routed to the dead letter queue
                if redelivery_count >= max_redelivery:
                    assert method_frame.redelivered == (message_id == "5")  # Check if the message is redelivered
                    assert (
                        seen_messages[message_id] >= max_redelivery
                    ), f"Message with ht_id={message_id} was redelivered more than {max_redelivery} times"
                    break
            else:
                logger.info("The queue is empty: Test ended")
                break

        # Now you can assert that a message ht_id=5 has been seen more than once
        assert seen_messages["5"] > 1, "Message with ht_id=5 was not redelivered"

        consumer_channel.queue_purge(consumer_instance.queue_name)
        consumer_channel_factory.close_channel()