from gi.repository import Gst
import sys
from sslog import logger

def _ctrl_c_handling(pipeline):
    """
    Exit and dump the pipeline graph. Usage example:

    import signal

    signal.signal(signal.SIGINT, ctrl_c_handling)
    """
    def __ctrl_c_handling(signal, frame):
        Gst.debug_bin_to_dot_file_with_ts(pipeline, Gst.DebugGraphDetails.ALL, '-pad')
        sys.exit(0)

    return __ctrl_c_handling

import collections
# http://stackoverflow.com/questions/2158395/flatten-an-irregular-list-of-lists-in-python
def flatten(l):
    for el in l:
        if isinstance(el, collections.Iterable) and not isinstance(el, basestring):
            for sub in flatten(el):
                yield sub
        else:
            yield el

def _logme(f):
    def __logme(*args, **kwargs):
        logger.debug('-> %s' % f.func_name)
        f(*args, **kwargs)
        logger.debug('   %s -->' % f.func_name)

    return __logme
