import logging

# FIXME: globals are evils
stream = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s - %(filename)s:%(lineno)d - %(message)s')

logger = logging.getLogger(__file__)
def get_level():
    from os import environ

    if environ.has_key('SS_LOG_LEVEL'):
        return getattr(logging, environ.get('SS_LOG_LEVEL'))
    else:
        return logging.DEBUG
logger.setLevel(get_level())
logger.addHandler(stream)
stream.setFormatter(formatter)

