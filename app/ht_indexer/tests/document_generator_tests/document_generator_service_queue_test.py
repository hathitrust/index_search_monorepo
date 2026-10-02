import json
import os
from typing import Any
from unittest.mock import Mock, patch

from conftest import create_test_queue_config
from document_generator.document_generator_service import DocumentGeneratorService
from ht_queue_service.queue_producer import QueueProducer


class TestDocumentGeneratorServiceQueueIntegration:
    """Drives DocumentGeneratorService through a live RabbitMQ queue via
    start_consuming() -> process_batch(), the same way queue_multiple_consumer_test.py
    exercises DocumentIndexerQueueService. generate_full_text_entry/publish_document are
    patched out -- this is about the queue plumbing (consume, ack, reject) that moved
    from QueueConsumer to QueueMultipleConsumer, not full-text generation itself, which
    is covered by document_generator_service_test.py and full_text_document_generator_test.py.
    """

    def test_process_batch_consumes_and_acks_message_on_success(
        self,
        get_global_queue_config: dict[str, Any],
        get_app_queue_config: dict[str, Any],
    ) -> None:
        queue_name = "test_generator_service_consume_success"
        queue_config, global_path, app_path = create_test_queue_config(
            get_global_queue_config,
            get_app_queue_config,
            queue_name,
            batch_size=1,
            requeue_message=False,
            shutdown_on_empty_queue=True,
        )

        producer_instance = QueueProducer(queue_config.queue_params)
        if not producer_instance.queue_manager.is_ready(producer_instance.channel):
            producer_instance.queue_reconnect()
        assert producer_instance.channel is not None
        producer_instance.channel.queue_purge(producer_instance.queue_manager.queue_name)

        message = {"ht_id": "mdp.39015078560292"}
        producer_instance.publish_messages(message)
        producer_instance.channel.close()
        assert producer_instance.channel_creator.connection.queue_connection is not None
        producer_instance.channel_creator.connection.queue_connection.close()

        db_conn = Mock()
        service = DocumentGeneratorService(db_conn, queue_config.queue_params, None, tgt_local=True)

        with (
            patch.object(
                service, "generate_full_text_entry", return_value={"id": message["ht_id"]}
            ),
            patch.object(service, "publish_document"),
        ):
            service.start_consuming()

        # generate_document ran end to end: MySQL status written, message acked and
        # removed from the queue (not left unacked or dead-lettered).
        db_conn.update_status.assert_called_once()
        assert service.channel is not None
        assert service.queue_manager.get_total_messages(service.channel) == 0

        service.channel.close()
        assert service.channel_creator.connection.queue_connection is not None
        service.channel_creator.connection.queue_connection.close()

        os.remove(global_path)
        os.remove(app_path)

    def test_process_batch_dead_letters_message_on_generation_failure(
        self,
        get_global_queue_config: dict[str, Any],
        get_app_queue_config: dict[str, Any],
    ) -> None:
        queue_name = "test_generator_service_consume_failure"
        queue_config, global_path, app_path = create_test_queue_config(
            get_global_queue_config,
            get_app_queue_config,
            queue_name,
            batch_size=1,
            requeue_message=False,
            shutdown_on_empty_queue=True,
        )

        producer_instance = QueueProducer(queue_config.queue_params)
        if not producer_instance.queue_manager.is_ready(producer_instance.channel):
            producer_instance.queue_reconnect()
        assert producer_instance.channel is not None
        producer_instance.channel.queue_purge(producer_instance.queue_manager.queue_name)

        message = {"ht_id": "mdp.39015078560292"}
        producer_instance.publish_messages(message)
        producer_instance.channel.close()
        assert producer_instance.channel_creator.connection.queue_connection is not None
        producer_instance.channel_creator.connection.queue_connection.close()

        db_conn = Mock()
        service = DocumentGeneratorService(db_conn, queue_config.queue_params, None, tgt_local=True)

        with patch.object(
            service, "generate_full_text_entry", side_effect=FileNotFoundError("zip not found")
        ):
            service.start_consuming()

        db_conn.update_status.assert_called_once()
        assert service.channel is not None

        # requeue_message=False means the rejected message was dead-lettered, not
        # returned to the main queue -- confirm it landed in the DLQ.
        dlx_channel = service.channel_creator.get_channel()
        assert dlx_channel is not None
        dlq_name = f"{service.queue_manager.queue_name}_dlq"
        list_ids: list[Any] = []
        for method_frame, _properties, body in service.consume_dead_letter_messages(
            dlx_channel, inactivity_timeout=5, queue_name=dlq_name
        ):
            if method_frame:
                list_ids.append(json.loads(body.decode("utf-8")).get("ht_id"))
                service.positive_acknowledge(dlx_channel, method_frame.delivery_tag)
            else:
                break
        assert list_ids == [message["ht_id"]]

        dlx_channel.close()
        service.channel.close()
        assert service.channel_creator.connection.queue_connection is not None
        service.channel_creator.connection.queue_connection.close()

        os.remove(global_path)
        os.remove(app_path)
