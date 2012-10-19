import logging

# FIXME: globals are evils
stream = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

logger = logging.getLogger('miao')
logger.setLevel(logging.DEBUG)
logger.addHandler(stream)
stream.setFormatter(formatter)

