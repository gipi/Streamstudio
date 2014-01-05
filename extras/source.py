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

Gst.init(None)


class Source(object):
    def __init__(self, path):
        """Initialize the object using the gstdiscover module.

        Documentation at <http://gstreamer.freedesktop.org/data/doc/gstreamer/head/gst-plugins-base-libs/html/gst-plugins-base-libs-gstdiscoverer.html>
        """
        self.path = path
        discoverer = GstPbutils.Discoverer()

        self.info = discoverer.discover_uri(self.path)

        self.audio = self.info.get_audio_streams()
        self.video = self.info.get_video_streams()

    def get_audio_mimetypes(self):
        """Get a list with the audio mimetypes available"""
        return [x.get_caps().to_string().split(',')[0] for x in self.audio]

    def get_video_mimetypes(self):
        """Get a list with the video mimetypes available"""
        return [x.get_caps().to_string().split(',')[0] for x in self.video]

    def get_audio_mimetype(self):
        return self.audio.split(',')[0]

    def __unicode__(self):
        audio_mt = ','.join(self.get_audio_mimetypes())
        video_mt = ','.join(self.get_video_mimetypes())
        return '%s %s%s%s' % (
            self.path,
            'audio:%s' % audio_mt if audio_mt != "" else "",
            " " if (audio_mt != "" and video_mt != "") else "",
            'video:%s' % video_mt if video_mt != "" else "",
        )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print >> sys.stderr, "usage %s <filename>" % sys.argv[0]
        sys.exit(1)

    s = Source(sys.argv[1])
    print unicode(s)
