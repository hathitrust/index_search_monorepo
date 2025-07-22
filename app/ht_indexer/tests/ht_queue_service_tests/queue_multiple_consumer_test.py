import json
from collections import defaultdict
import pytest

from ht_queue_service.queue_multiple_consumer import QueueMultipleConsumer
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

class HTMultipleConsumerServiceConcrete(QueueMultipleConsumer):

    def __init__(self, user: str, password: str, host: str, queue_name: str, requeue_message: bool = False,
                 batch_size: int = 1, shutdown_on_empty_queue: bool = True, max_redelivery: int = 3):
        super().__init__(user, password, host, queue_name, requeue_message, batch_size, shutdown_on_empty_queue)

        self.consume_one_message = []
        self.shutdown_on_empty_queue = shutdown_on_empty_queue
        # These two variables are used to track the redelivery count and seen messages
        self.redelivery_count = 0  # Count how many times the message with ht_id=5 was redelivered
        self.seen_messages = defaultdict(int) # Dictionary to track how many times each message_id has been seen
        self.max_redelivery = max_redelivery  # maximum allowed redeliveries

    def process_batch(self, batch: list, delivery_tags: list) -> bool:

        try:
            list_id = [doc.get("ht_id") for doc in batch]

            # Increment count for each message_id
            for message_id in list_id:
                self.seen_messages[message_id] += 1

            received_messages = batch.copy()
            if "5" in list_id:
                try:
                    print(1 / 0)
                except Exception as e:
                    logger.error(f"Error in indexing document: {e}")
                    raise e

            # Acknowledge the message if the message is processed successfully
            for tag in delivery_tags:
                self.positive_acknowledge(self.channel, tag)
            self.consume_one_message = received_messages

            batch.clear()
            delivery_tags.clear()
        except Exception as e:
            logger.info(f"Message failed with error: {e}")
            failed_messages_tags = delivery_tags.copy()

            # Reject the message
            for delivery_tag in failed_messages_tags:
                self.reject_message(self.channel, delivery_tag)
            # If requeue_message is True, the message will be requeued to the main queue
            self.redelivery_count += 1

        # Check if the message with ht_id=5 has been seen more than max_redelivery times to stop consuming
        if "5" in self.seen_messages:
            # If the message with ht_id=5 is seen more than max_redelivery times, stop consuming
            if self.seen_messages["5"] >= self.max_redelivery:
                logger.info(f"Message with ht_id=5 was redelivered more than {self.max_redelivery} times.")
                return False
        return True


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

class TestHTMultipleQueueConsumer:

    def test_queue_consume_message(self, one_message, get_rabbit_mq_host_name):
        """ Test for consuming a message from the queue
        One message is published and consumed, then at the end of the test the queue is empty
        """
        queue_name = "multiple_test_queue_consume_message"

        # Create a producer instance to publish the message
        producer_instance = QueueProducer(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name=queue_name,
            batch_size=1
        )

        logger.info(f"Checking if the queue {queue_name} exists before publishing messages")

        # Clean up the queue
        if not producer_instance.queue_setup.is_ready():

            producer_instance.queue_reconnect()
            producer_instance.queue_setup.set_up_queue()

        # Clean up the queue
        producer_instance.channel.queue_purge(producer_instance.queue_name)

        # Publish the message to the queue
        producer_instance.publish_messages(one_message)

        logger.info(f"Closing the producer channel after publishing the message")
        producer_instance.channel.close()
        logger.info(f"Closing the producer connection")
        producer_instance.queue_connection.close()

        # Create a consumer instance to consume the message
        multiple_consumer_instance = HTMultipleConsumerServiceConcrete(user="guest",
                                                                       password="guest",
                                                                       host=get_rabbit_mq_host_name,
                                                                       queue_name="multiple_test_queue_consume_message",
                                                                       requeue_message=False,
                                                                       batch_size=1,
                                                                       shutdown_on_empty_queue=True,
                                                                       max_redelivery=1)

        # Create the channel
        logger.info(f"Creating the channel for the consumer instance: {multiple_consumer_instance.queue_name}")

        logger.info(f"Starting to consume messages from the queue: {multiple_consumer_instance.queue_name}")
        multiple_consumer_instance.start_consuming()


        output_message = multiple_consumer_instance.consume_one_message
        assert output_message[0] == one_message
        assert 1 == len(output_message)

        multiple_consumer_instance.channel.queue_purge(queue_name)
        logger.info(f"Closing the channel for the consumer instance: {multiple_consumer_instance.queue_name}")
        multiple_consumer_instance.channel.close()
        logger.info(f"Closing the queue connection")
        multiple_consumer_instance.queue_connection.close()

    def test_queue_consume_message_empty(self, get_rabbit_mq_host_name):
        """ Test for consuming a message from an empty queue"""

        multiple_consumer_instance = HTMultipleConsumerServiceConcrete(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name="multiple_test_queue_consume_message_empty",
            requeue_message=False,
            batch_size=1,
            shutdown_on_empty_queue=True,
            max_redelivery=1
        )

        multiple_consumer_instance.start_consuming()

        # The queue is empty, so consume 0 messages
        count_messages = 0
        for message in multiple_consumer_instance.consume_one_message:
            count_messages += 1
            logger.info(f"Consumed message: {message}")
        assert 0 == count_messages

        logger.info(f"Closing the channel for the consumer instance: {multiple_consumer_instance.queue_name}")
        multiple_consumer_instance.channel.close()
        logger.info(f"Closing the queue connection")
        multiple_consumer_instance.queue_connection.close()

    def test_queue_requeue_message_requeue_false(self, get_rabbit_mq_host_name, list_messages):
        """ Test for re-queueing a message from the queue, an error is raised, and all the 10 messages is routed
        to the dead letter queue and discarded from the main queue"""

        queue_name = "multiple_test_queue_requeue_message_requeue_false"

        # Create a producer instance to publish the message
        producer_instance = QueueProducer(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name= queue_name,
            batch_size=1
        )

        # Create a consumer instance to consume the message to simulate a failure that sends messages to the dead letter queue
        multiple_consumer_instance = HTMultipleConsumerServiceConcrete(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name=queue_name,
            requeue_message=False,
            batch_size=10,
            shutdown_on_empty_queue=True,
            max_redelivery=1
        )

        # Create the queue
        if not multiple_consumer_instance.queue_setup.is_ready():
            multiple_consumer_instance.queue_reconnect()
            multiple_consumer_instance.queue_setup.set_up_queue()

        # Clean up the queue
        multiple_consumer_instance.channel.queue_purge(multiple_consumer_instance.queue_name)

        # Create a new channel for the dead letter queue
        dlx_channel = multiple_consumer_instance.channel_creator.get_channel()
        # Clean up the dead letter queue
        dlx_channel.queue_purge(f"{multiple_consumer_instance.queue_name}_dlq")

        # Publish the message to the queue
        for message in list_messages:
            # Publish the message
            producer_instance.publish_messages(message)

        # Close the producer channel after publishing all messages
        logger.info(f"Closing the producer channel after publishing all messages")
        producer_instance.channel.close()

        logger.info(f"Closing the producer connection")
        producer_instance.queue_connection.close()

        # Start consuming messages from the main queue
        logger.info(f"Starting to consume messages from the queue: {multiple_consumer_instance.queue_name}")

        # Start consuming messages from the main queue
        multiple_consumer_instance.start_consuming()

        logger.info(f"DLQ NAME: {multiple_consumer_instance.queue_name}_dlq")

        # Running the test to consume messages from the dead letter queue
        list_ids = []
        # Consume messages from the dead letter queue
        for method_frame, properties, body in multiple_consumer_instance.consume_dead_letter_messages(dlx_channel,
            inactivity_timeout=5, queue_name=f"{multiple_consumer_instance.queue_name}_dlq"):
            if method_frame:
                output_message = json.loads(body.decode("utf-8"))
                logger.info(f"Message in dead letter queue: {output_message}")
                multiple_consumer_instance.positive_acknowledge(dlx_channel,
                                                                method_frame.delivery_tag)
                list_ids.append(output_message.get("ht_id"))
            else:
                logger.info("The dead letter queue is empty: Test ended")
                break

        logger.info(f"List of IDs consumed: {list_ids}")
        assert len(list_ids) == 10
        assert list_ids == ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"], \
            "The messages in the dead letter queue do not match the expected IDs"

        logger.info(f"Deleting all messages in the dead letter queue: {multiple_consumer_instance.queue_name}_dlq")
        multiple_consumer_instance.channel.queue_purge(f"{multiple_consumer_instance.queue_name}_dlq")
        # Close the channel
        logger.info(f"Closing the channel for the dead letter queue: {multiple_consumer_instance.queue_name}_dlq")
        dlx_channel.close()

        # Close the consumer channel
        logger.info(f"Closing the channel for the main queue: {multiple_consumer_instance.queue_name}")
        multiple_consumer_instance.channel.queue_purge(multiple_consumer_instance.queue_name)

        logger.info(f"Closing the channel for the main queue: {multiple_consumer_instance.queue_name}")
        multiple_consumer_instance.channel.close()

        logger.info(f"Closing the queue connection")
        multiple_consumer_instance.queue_connection.close()

    def test_queue_requeue_message_requeue_true(self, get_rabbit_mq_host_name, list_messages):
        """ Test for re-queueing a message from the queue, an error is raised, and instead of routing the message
        to the dead letter queue, it is requeue to the main queue """

        queue_name = "multiple_queue_requeue_message_requeue_true"
        # Create a producer instance to publish the message
        producer_instance = QueueProducer(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name=queue_name,
            batch_size=1
        )

        logger.info(f"Checking if the queue {queue_name} exists before publishing messages")
        # Clean up the queue
        if not producer_instance.queue_setup.is_ready():

            producer_instance.queue_reconnect()
            producer_instance.queue_setup.set_up_queue()

        # Clean up the queue
        producer_instance.channel.queue_purge(producer_instance.queue_name)


        # Create a consumer instance to consume the message to simulate a failure that sends messages to the dead letter queue
        multiple_consumer_instance = HTMultipleConsumerServiceConcrete(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name=queue_name,
            requeue_message=True,
            batch_size=10,
            shutdown_on_empty_queue=True,
            max_redelivery=3
        )

        # Clean up the queue
        multiple_consumer_instance.channel.queue_purge(multiple_consumer_instance.queue_name)

        # Publish the message to the queue
        for message in list_messages:
            # Publish the message
            producer_instance.publish_messages(message)

        # Close the producer channel after publishing all messages
        logger.info(F"Closing the producer channel after publishing all messages")
        producer_instance.channel.close()
        logger.info(f"Closing the producer connection")
        producer_instance.queue_connection.close()

        logger.info(f"Starting to consume messages from the queue: {multiple_consumer_instance.queue_name}")
        multiple_consumer_instance.start_consuming()

        assert multiple_consumer_instance.redelivery_count >= multiple_consumer_instance.max_redelivery  # Since we have 10 messages and the error occurs on the 5th message, it should be redelivered 3 times

        logger.info(f"Queue cleanup: Deleting all messages in the queue: {multiple_consumer_instance.queue_name}")
        multiple_consumer_instance.channel.queue_purge(multiple_consumer_instance.queue_name)
        logger.info(f"Closing the channel for the main queue: {multiple_consumer_instance.queue_name}")
        multiple_consumer_instance.channel.close()

        logger.info(f"Closing the queue connection")
        multiple_consumer_instance.queue_connection.close()