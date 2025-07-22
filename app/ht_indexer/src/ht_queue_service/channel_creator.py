import pika
from ht_queue_service.queue_connection import QueueConnection
from ht_queue_service.queue_connection import QueueConnectionError
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

class ChannelCreator:
    def __init__(self, connection: QueueConnection):
        self.connection = connection # The connection to RabbitMQ

    def get_channel(self):

        try:
            # Checking connection status before creating a channel
            if not self.connection or self.connection.queue_connection.is_closed:
                logger.error(f"RabbitMQ connection is not established or is closed.")
            else:
                channel = self.connection.queue_connection.channel()
                logger.info("Channel created successfully.")
                return channel
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