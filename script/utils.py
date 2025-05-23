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
        duration = te - ts

        # Store timing info in the result if it's a tuple, otherwise create a tuple
        if isinstance(result, tuple):
            return result + (duration,)
        else:
            return (result, duration)
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
