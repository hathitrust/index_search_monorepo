import json
from collections import defaultdict

import pytest
from ht_queue_service.queue_multiple_consumer import QueueMultipleConsumer
from ht_queue_service.queue_producer import QueueProducer
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

class HTMultipleConsumerServiceConcrete(QueueMultipleConsumer):

    def __init__(self, user: str, password: str, host: str, queue_name: str, requeue_message: bool = False,
                 batch_size: int = 1, shutdown_on_empty_queue: bool = True):
        super().__init__(user, password, host, queue_name, requeue_message, batch_size, shutdown_on_empty_queue)
        self.consume_one_message = []
        self.shutdown_on_empty_queue = shutdown_on_empty_queue
        # These two variables are used to track the redelivery count and seen messages
        self.redelivery_count = 0  # Count how many times the message with ht_id=5 was redelivered
        self.seen_messages = defaultdict(int) # Dictionary to track how many times each message_id has been seen
        self.max_redelivery = 3  # maximum allowed redeliveries

    def process_batch(self, batch: list, delivery_tags: list):

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
                self.positive_acknowledge(self.ht_channel, tag)
            self.consume_one_message = received_messages

            batch.clear()
            delivery_tags.clear()
        except Exception as e:
            logger.info(f"Message failed with error: {e}")
            failed_messages_tags = delivery_tags.copy()

            # Reject the message
            for delivery_tag in failed_messages_tags:
                self.reject_message(self.ht_channel, delivery_tag)
            # If requeue_message is True, the message will be requeued to the main queue
            self.redelivery_count += 1
        #time.sleep(1)
        # Stop consuming if the flag is set
        if self.shutdown_on_empty_queue and self.get_total_messages() == 0:
            logger.info("Stopping consumer...")
            self.ht_channel.stop_consuming()
            return False

        # Check if the message with ht_id=5 has been seen more than max_redelivery times to stop consuming
        if "5" in self.seen_messages:
            # If the message with ht_id=5 is seen more than max_redelivery times, stop consuming
            if self.seen_messages["5"] >= self.max_redelivery:
                logger.info(f"Message with ht_id=5 was redelivered more than {self.max_redelivery} times. Stopping consumer.")
                self.ht_channel.stop_consuming()
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

        # Create a producer instance to publish the message
        producer_instance = QueueProducer(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name="multiple_test_queue_consume_message",
            batch_size=1,
        )

        # Publish the message to the queue
        producer_instance.publish_messages(one_message)

        # Create a consumer instance to consume the message
        multiple_consumer_instance = HTMultipleConsumerServiceConcrete(user="guest",
                                                                       password="guest",
                                                                       host=get_rabbit_mq_host_name,
                                                                       queue_name="multiple_test_queue_consume_message",
                                                                       requeue_message=False,
                                                                       batch_size=1)

        multiple_consumer_instance.start_consuming()

        output_message = multiple_consumer_instance.consume_one_message

        assert output_message[0] == one_message

        assert 1 == len(output_message)

    def test_queue_consume_message_empty(self, get_rabbit_mq_host_name):
        """ Test for consuming a message from an empty queue"""

        multiple_consumer_instance = HTMultipleConsumerServiceConcrete(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name="multiple_test_queue_consume_message_empty",
            requeue_message=False,
            batch_size=1,
        )

        multiple_consumer_instance.start_consuming()

        # The queue is empty, so consume 0 messages
        count_messages = 0
        for message in multiple_consumer_instance.consume_one_message:
            count_messages += 1
            logger.info(f"Consumed message: {message}")
        assert 0 == count_messages

    def test_queue_requeue_message_requeue_false(self, get_rabbit_mq_host_name, list_messages):
        """ Test for re-queueing a message from the queue, an error is raised, and all the 10 messages is routed
        to the dead letter queue and discarded from the main queue"""

        # Create a producer instance to publish the message
        producer_instance = QueueProducer(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name="multiple_test_queue_requeue_message_requeue_false",
            batch_size=1
        )

        producer_instance.ht_channel.queue_purge(
            f"{producer_instance.queue_name}_dead_letter_queue"
        )

        # Publish the message to the queue
        for message in list_messages:
            # Publish the message
            producer_instance.publish_messages(message)

        # Create a consumer instance to consume the message to simulate a failure that sends messages to the dead letter queue
        multiple_consumer_instance = HTMultipleConsumerServiceConcrete(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name="multiple_test_queue_requeue_message_requeue_false",
            requeue_message=False,
            batch_size=10,
        )

        multiple_consumer_instance.start_consuming()

        logger.info(f"DLQ NAME: {multiple_consumer_instance.queue_name}_dead_letter_queue")

        # Running the test to consume messages from the dead letter queue
        list_ids = []
        # Consume messages from the dead letter queue
        for method_frame, properties, body in multiple_consumer_instance.dlx_channel.consume(
            f"{multiple_consumer_instance.queue_name}_dead_letter_queue",
            inactivity_timeout=5,
        ):
            if method_frame:
                output_message = json.loads(body.decode("utf-8"))
                logger.info(f"Message in dead letter queue: {output_message}")

                list_ids.append(output_message.get("ht_id"))
            else:
                logger.info("The dead letter queue is empty: Test ended")
                break

        logger.info(f"List of IDs consumed: {list_ids}")
        assert len(list_ids) == 10
        assert list_ids == ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"], \
            "The messages in the dead letter queue do not match the expected IDs"

        multiple_consumer_instance.ht_channel.queue_purge(
            f"{multiple_consumer_instance.queue_name}_dead_letter_queue"
        )

    def test_queue_requeue_message_requeue_true(self, get_rabbit_mq_host_name, list_messages):
        """ Test for re-queueing a message from the queue, an error is raised, and instead of routing the message
        to the dead letter queue, it is requeue to the main queue

        The published messages appear in the main queue with status Ready, when the consumer consumes the messages,
        all the messages will have status Unacked until the consumer acknowledges the messages.
        In this test, when the consumer consumes the message with ht_id=5, it raises an error, so RabbitMQ will put
         the 10 messages back into the front of the queue, making it eligible for immediate redelivery. so
         the consumer will consume them again, increasing
        the redelivery count for all the messages. If we do not limit the redelivery attempts the message loops
        endlessly.
        On this test, we set the maximum redelivery count to 3, so the consumer will stop, and we purge the queue.
        We manually stop the consumer after the redelivery count is higher than 3.
        """

        # Create a producer instance to publish the message
        producer_instance = QueueProducer(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name="multiple_queue_requeue_message_requeue_true",
            batch_size=1
        )

        producer_instance.ht_channel.queue_purge(producer_instance.queue_name)

        # Publish the message to the queue
        for message in list_messages:
            # Publish the message
            producer_instance.publish_messages(message)

        # Create a consumer instance to consume the message to simulate a failure that sends messages to the dead letter queue
        multiple_consumer_instance = HTMultipleConsumerServiceConcrete(
            user="guest",
            password="guest",
            host=get_rabbit_mq_host_name,
            queue_name="multiple_queue_requeue_message_requeue_true",
            requeue_message=True,
            batch_size=10,
        )

        multiple_consumer_instance.start_consuming()
        # Since we have 10 messages and the error occurs on the 5th message, it should be redelivered 3 times
        assert multiple_consumer_instance.redelivery_count >= multiple_consumer_instance.max_redelivery

        multiple_consumer_instance.ht_channel.queue_purge(multiple_consumer_instance.queue_name)