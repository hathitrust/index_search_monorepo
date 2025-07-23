import pytest
from ht_queue_service.channel_factory import ChannelFactory

class TestChannelFactory:
    """ Test the QueueConnection class """

    def test_create_channel_close(self, rabbit_mq_connection, get_rabbit_mq_host_name):

        channel_factory = ChannelFactory(rabbit_mq_connection)
        assert channel_factory.channel is not None
        assert channel_factory.channel.is_open
        # Closing the channel
        channel_factory.close_channel()
        assert channel_factory.channel.is_closed
        assert channel_factory.channel is None