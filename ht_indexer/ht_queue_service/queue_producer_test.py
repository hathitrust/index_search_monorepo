import pytest

from ht_queue_service.queue_producer import QueueProducer
import multiprocessing
import time
import copy

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


class TestHTProducerService:
    def test_queue_produce_one_message(self):
        ht_producer = QueueProducer("guest",
                                    "guest",
                                    "rabbitmq",
                                    "test_producer_queue")

        ht_producer.publish_messages(message)

    def test_multiprocessing_producer(self, create_list_message):
        print(f" Running with {PROCESSES} processes")
        start = time.time()
        with multiprocessing.Pool(PROCESSES) as p:
            p.map_async(
                self.test_queue_produce_one_message,
                create_list_message
            )
            # clean up
            p.close()
            p.join()

        print(f"Time taken = {time.time() - start:.10f}")
