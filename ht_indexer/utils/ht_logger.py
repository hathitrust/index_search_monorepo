import logging, sys


def get_ht_logger(name=__name__, log_level=logging.INFO):  # Create a logger named ‘app’
    logger = logging.getLogger(name)

    # set the logging format
    log_format = "%(asctime)s  :: %(name)s :: %(levelname)s :: %(message)s"

    # Set the threshold logging level of the logger to INFO
    # set the logging level based on the user selection
    if log_level == "INFO":
        logger.setLevel(logging.INFO)
    elif log_level == "ERROR":
        logger.setLevel(logging.ERROR)
    elif log_level == "DEBUG":
        logger.setLevel(logging.DEBUG)
    elif log_level == "WARNING":
        logger.setLevel(logging.WARNING)
    # logger.setLevel(log_level)
    # Create a stream-based handler that writes the log entries    #into the standard output stream
    handler = logging.StreamHandler(sys.stdout)
    # Create a formatter for the logs
    formatter = logging.Formatter(log_format)
    # Set the created formatter as the formatter of the handler
    handler.setFormatter(formatter)
    # Add the created handler to this logger
    logger.addHandler(handler)

    return logger
