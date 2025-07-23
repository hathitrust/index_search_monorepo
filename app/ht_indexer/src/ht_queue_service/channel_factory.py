import pika
from queue_connection import QueueConnectionError
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

class ChannelFactory:
    def __init__(self, connection: pika.BlockingConnection):
        self.connection = connection
        self.channel = None

    def get_channel(self):

        try:
            # Checking connection status before creating a channel
            if not self.connection or self.connection.is_closed:
                logger.error(f"RabbitMQ connection is not established or is closed.")
            else:
                self.channel = self.connection.channel()
                logger.info("Channel created successfully.")
                return self.channel
        except pika.exceptions.ChannelClosed as e:
            logger.error(f"Error creating RabbitMQ channel: {e}")
        except pika.exceptions.ChannelClosedByBroker as e:
            logger.error(f"Broker closed the channel: {e}")
        except pika.exceptions.ChannelWrongStateError as e:
            logger.error(f"Channel is in the wrong state: {e}")
        except pika.exceptions.NoFreeChannels as e:
            logger.error(f"No free channels available: {e}")
        except pika.exceptions.AMQPError as e:
            logger.error(f"AMQP error while setting up queue: {e}")
        except Exception as e:
            raise QueueConnectionError(f"Unexpected error during queue setup: {e}")
        return None



    def close_channel(self):
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
                logger.info("RabbitMQ main channel closed.")
        except pika.exceptions.ChannelClosed as e:
            logger.warning(f"Error closing RabbitMQ main channel: {e}")
        except Exception as e:
            logger.error(f"Unexpected error while closing RabbitMQ main channel: {e}")
        finally:
            self.channel = None
            logger.info("Main channel set to None after closing.")