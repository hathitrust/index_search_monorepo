# producer
import json

import pika.exceptions
from ht_utils.ht_logger import get_ht_logger

from ht_queue_service.queue_connection import QueueConnection

logger = get_ht_logger(name=__name__)


class QueueProducer(QueueConnection):
    """ Create a class to send messages to a rabbitMQ """

    def __init__(self, user: str, password: str, host: str, queue_name: str, batch_size: int = 1):
        """

        :param user: username for the RabbitMQ
        :param password: password for the RabbitMQ
        :param host: host for the RabbitMQ
        :param queue_name: name of the queue
        """
        # Define credentials (user/password) as environment variables
        # declaring the credentials needed for connection like host, port, username, password, exchange etc

        super().__init__(user, password, host, queue_name, batch_size)

        #self.ht_channel.confirm_delivery = True  # Enable publisher confirms for message delivery
        #try:
        #    self.dlq_conn =  QueueConnectionDeadLetter(user, password, self.host, self.queue_name, batch_size)
        #except Exception as e:
        #    logger.error(
        #        f"Failed to create dead-letter queue connection for {self.queue_name}: {e}"
        #    )
        #    raise

    def publish_messages(self, queue_message: dict, auto_close=False) -> None:

        """
        Publish a message to the RabbitMQ queue.
        Any process that use this method should close the connection when it is done and set auto_close to False.

        :param queue_message: The message to be published, should be a dictionary.
        :param auto_close: If True, the connection will be closed after publishing the message.
        """

        try:

            if not self.ht_channel or self.ht_channel.is_closed:
                self.queue_reconnect()

            try:
                body = json.dumps(queue_message)
            except (TypeError, ValueError) as json_err:
                logger.error(
                    f"Failed to serialize message {queue_message.get('ht_id')}: {json_err}", exc_info=True
                )
                raise

            self.ht_channel.basic_publish(
                exchange=self.exchange, routing_key=self.queue_name, body=body,
                properties=pika.BasicProperties(delivery_mode=2,  # make the message persistent
                                                content_type="application/json")
            )
            logger.info(f"Published message to {self.queue_name}: {body}")

        except (pika.exceptions.ChannelClosed, pika.exceptions.ConnectionClosed) as err:
            logger.warning(f"RabbitMQ connection/channel closed: {err}. Reconnecting...")
            self.queue_reconnect()
            raise

        except Exception as err:
            logger.error(
                f"Failed to publish message {queue_message.get('ht_id')}: {err}", exc_info=True
            )
            raise

        finally:
            if auto_close:
                try:
                    self.close()
                    logger.info("RabbitMQ connection closed.")
                except Exception as close_err:
                    logger.warning(f"Error closing RabbitMQ connection: {close_err}")
