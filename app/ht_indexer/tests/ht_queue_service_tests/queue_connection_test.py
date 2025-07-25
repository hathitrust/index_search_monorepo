import pytest

class TestQueueConnection:
    """ Test the QueueConnection class """

    def test_real_connect_and_close(self, rabbit_mq_connection):
        assert rabbit_mq_connection.queue_connection.is_open
        rabbit_mq_connection.close()
        assert rabbit_mq_connection.queue_connection is None

