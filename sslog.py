import logging

# FIXME: globals are evils
stream = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s - %(filename)s:%(lineno)d - %(message)s')

logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)
logger.addHandler(stream)
stream.setFormatter(formatter)

