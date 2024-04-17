import json

from ht_queue_service.queue_consumer import QueueConsumer
from ht_queue_service.queue_producer import QueueProducer


class TestHTConsumerService:
    def test_queue_consume_message(self):
        message = {"ht_id": "1234", "ht_title": "Hello World", "ht_author": "John Doe"}
        ht_producer = QueueProducer("guest",
                                    "guest",
                                    "rabbitmq",
                                    "test_producer_queue")

        ht_producer.publish_messages(message)

        queue_consumer = QueueConsumer("guest",
                                       "guest",
                                       "rabbitmq",
                                       "test_producer_queue")

        for method_frame, properties, body in queue_consumer.conn.ht_channel.consume('test_producer_queue'):
            # Display the message parts
            output_message = json.loads(body.decode('utf-8'))
            assert message == output_message
            break

    def test_queue_consume_message_empty(self):

        queue_consumer = QueueConsumer("guest",
                                       "guest",
                                       "rabbitmq",
                                       "test_producer_queue")

        for message in queue_consumer.consume_message(inactivity_timeout=3):
            print(message)
        assert 0 == queue_consumer.get_total_messages()
