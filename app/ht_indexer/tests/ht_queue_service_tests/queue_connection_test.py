from typing import Any

from ht_queue_service.queue_connection import QueueConnection


class TestQueueConnection:
    """ Test the QueueConnection class """

    def test_real_connect_and_close(self, get_global_queue_config: dict[str, Any], get_rabbit_mq_host_name) -> None:
        """ Test the connection to RabbitMQ and closing it
        :param get_global_queue_config: Fixture to get the global queue configuration
        :return: None
        """

        rabbit_mq_connection = QueueConnection(user=get_global_queue_config.get("user", "guest"),
                                               password=get_global_queue_config.get("password", "guest"),
                                               host=get_rabbit_mq_host_name)

        assert rabbit_mq_connection.queue_connection.is_open
        rabbit_mq_connection.close()
        assert rabbit_mq_connection.queue_connection is None

