"""
Module to manage video/audio source internally to streamstudio

The Source class take a path as argument in its constructor
and build an instance with all the data necessary to attach
to the StreamStudio pipeline.

    >>> source = Source('/path/to/video/file.mp4')
    >>> source.info
    {'audio': True, 'video': True, 'path': '/path/to/video/file.mp4'}
"""
from gi.repository import Gst, GObject, GstPbutils
import sys
import gi
gi.require_version('Gst', '1.0')


class Source(object):
    def __init__(self, path):
        self.path = path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print >> sys.stderr, "usage %s <filename>" % sys.argv[0]
        sys.exit(1)

    Gst.init(None)
    GObject.threads_init()
    #discover(sys.argv[1])
    discoverer = GstPbutils.Discoverer()
    info = discoverer.discover_uri(sys.argv[1])

    # video info
    print '# video'
    for vinfo in info.get_video_streams():
        print vinfo.get_caps().to_string().replace(', ', '\n\t')

    # audio info
    print '# audio'
    for ainfo in info.get_audio_streams():
        print ainfo.get_caps().to_string().replace(', ', '\n\t')
