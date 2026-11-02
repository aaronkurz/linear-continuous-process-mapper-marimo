import logging


def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)  # Set the minimum logging level

    # Create console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Add formatter to console handler
    ch.setFormatter(formatter)

    # Add console handler to logger
    if not logger.handlers:
        logger.addHandler(ch)

    return logger
