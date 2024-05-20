import pytest

from ht_queue_service.queue_producer import QueueProducer
import multiprocessing
import time
import copy

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

PROCESSES = multiprocessing.cpu_count() - 1

message = {"ht_id": "1234", "ht_title": "Hello World", "ht_author": "John Doe"}


@pytest.fixture
def create_list_message():
    list_message = []
    for i in range(100):
        new_message = copy.deepcopy(message)
        new_message["ht_id"] = f"{new_message['ht_id']}_{i}"
        list_message.append(message)
    return list_message


@pytest.fixture
def queue_parameters(request):
    """
    This function is used to create the parameters for the queue
    """
    return request.param


@pytest.fixture
def producer_instance(queue_parameters):
    """
    This function is used to generate a message
    """

    return QueueProducer(queue_parameters["user"], queue_parameters["password"],
                         queue_parameters["host"], queue_parameters["queue_name"],
                         queue_parameters["dead_letter_queue"])


class TestHTProducerService:
    @pytest.mark.parametrize("queue_parameters", [{"user": "guest", "password": "guest", "host": "rabbitmq",
                                                   "queue_name": "test_producer_queue", "dead_letter_queue": True}])
    def test_queue_produce_one_message(self, producer_instance):
        producer_instance.publish_messages(message)
        assert producer_instance.conn.get_total_messages() == 1
        producer_instance.conn.ht_channel.queue_purge(producer_instance.queue_name)

    def test_multiprocessing_producer(self, create_list_message):
        logger.info(f" Running with {PROCESSES} processes")
        start = time.time()
        with multiprocessing.Pool(PROCESSES) as p:
            p.map_async(
                self.test_queue_produce_one_message,
                create_list_message
            )
            # clean up
            p.close()
            p.join()

        logger.info(f"Time taken = {time.time() - start:.10f}")

    @pytest.mark.parametrize("queue_parameters", [{"user": "guest", "password": "guest", "host": "rabbitmq",
                                                   "queue_name": "test_producer_queue", "dead_letter_queue": True}])
    def test_queue_reconnect(self, producer_instance):
        # Check if the connection is open
        assert producer_instance.conn.queue_connection.is_open

        # Close the connection
        producer_instance.conn.queue_connection.close()

        # Check if the connection is closed
        assert not producer_instance.conn.queue_connection.is_open

        # Reconnect
        producer_instance.conn.queue_reconnect()

        # Check if the connection is open
        assert producer_instance.conn.queue_connection.is_open
