import sys
import time
import logging

from functools import wraps


def timing(f):
    @wraps(f)
    def wrap(*args, **kw):
        ts = time.time()
        result = f(*args, **kw)
        te = time.time()
        logger.debug('func {} args [{}, {}] took: {:.2f} sec'.format(f.__name__, args, kw, te-ts))
        return result
    return wrap

def createLogger(debug=False):
    logLevel = logging.DEBUG if debug else logging.INFO

    _format = '[%(asctime)s] %(levelname)s %(message)s'
    formatter = logging.Formatter(_format)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)

    logger = logging.getLogger('tafor-layer')
    logger.setLevel(logLevel)
    logger.addHandler(ch)

    return logger


logger = createLogger(debug=True)
