import arrow


def get_current_time(current=None, str_format: str = "YYYY-MM-DD HH:mm:ss"):
    """
    Returns the current time in the format HH:MM:SS.
    :param current: The current time
    :param str_format: The format of the time to return
    """
    if current is None:
        current = arrow.now()

    return str(current.format(str_format))


def get_general_error_message(service_name: str, e: Exception) -> dict:
    """
    Returns an error dictionary with information about the cause of the error
    :param service_name: The name of the service that raised the error
    :param e: The exception
    """

    return {'service_name': service_name,
            'error_message': e,
            'timestamp': get_current_time()
            }


def get_error_message_by_document(service_name: str, e: Exception, doc: dict) -> dict:
    """
    Returns an error dictionary with information about
    a specific document and the cause of the error

    :param service_name: The name of the service that raised the error
    :param e: The exception
    :param doc: The document, the document is a dictionary that
     must have a key 'ht_id'
    """
    # TODO Check if in the future we want to add more information about the document, like the record_id or probably
    # the full message received from the queue or the full document
    return {'service_name': service_name,
            'error_message': e,
            'ht_id': doc.get('ht_id'),
            'timestamp': get_current_time()
            }
