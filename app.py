from gi.repository import GObject, Gst
import sys
from sslog import logger
# lock use inspired from this <https://github.com/kivy/kivy/blob/31ba89c6c7661dcc6fa6916b46be8a0381874e5c/kivy/core/video/video_gstreamer.py>
from threading import Lock

GObject.threads_init()
g_main_loop = GObject.MainLoop()
Gst.init(None)


class Main:
    def __init__(self, pipeline_string='videotestsrc pattern=18 ! tee name=t ! queue ! autovideosink t. ! queue ! videoconvert ! videorate ! video/x-raw,width=(int)320,height=(int)240,format=(string)RGB16,framerate=(fraction)30/1 ! appsink name=sink'):
        self.data = None# this will contain the data passed between
        self.source_id = None
        self.lock = Lock()

        self.isWhite = True
        self.isStream = True
        self.timestamp = 0

        self.pipeline = Gst.parse_launch(pipeline_string)

        self.appsink = self.pipeline.get_by_name('sink')

        assert self.appsink, 'appsink element named \'sink\' not found'

        self.appsink.connect('new-sample', self.on_new_buffer)
        self.appsink.set_property('emit-signals', True)

        self.pipeline.set_state(Gst.State.PLAYING)

        # OUTPUT pipeline
        self.pipeline_out = Gst.parse_launch('appsrc name=source ! videoconvert ! autovideosink')

        self.appsrc = self.pipeline_out.get_by_name('source')

        assert self.appsrc, 'appsrc element named \'source\' not found'

        self.appsrc.set_property('caps', Gst.Caps.from_string('video/x-raw,format=(string)RGB16,width=(int)320,height=(int)240,framerate=(fraction)30/1'))

        self.appsrc.connect('need-data', self.on_need_data)
        self.appsrc.connect('enough-data', self.on_enough_data)

        self.pipeline_out.set_state(Gst.State.PLAYING)

        GObject.timeout_add_seconds(2, self._switch_data_type)

    def on_new_buffer(self, appsink):
        with self.lock:
            bffer = appsink.emit('pull-sample')
            self.data = bffer
        # logger.info('. %s' % buffer.get_caps().to_string())
        logger.debug('pulled %s' % self.data)

    def on_need_data(self, source, *args):
        logger.debug('on_need_dat')
        if not self.source_id:
            self.source_id = GObject.idle_add(self.push_data, source)

    def _switch_data_type(self):
        self.isStream = not self.isStream
        if not self.isStream:
            self.isWhite = not self.isWhite

        logger.debug('switched to stream: %s and white: %s' % (self.isStream, self.isWhite,))

        # recall us again, over and over again dude
        return True

    def build_white_black_stream(self, width, height, depth):
        logger.debug('white: %s' % self.isWhite)
        # http://gstreamer.freedesktop.org/data/doc/gstreamer/head/manual/html/section-data-spoof.html#section-spoof-appsrc
        size = width * height * depth
        bffer = Gst.Buffer.new_allocate(None, size, None)

        bffer.memset(0, 0x08 if self.isWhite else 0xf8, size)

        bffer.pts = self.timestamp
        bffer.duration = Gst.util_uint64_scale_int(1, Gst.SECOND, 30)

        # NOTE: if you remove this line below the stream after the first
        # switch doesn't re-switch and the stream appears lagging
        self.timestamp += bffer.duration

        return bffer

    def copy_from_data(self):
        with self.lock:
            if not self.data:
                return None

            bffer = self.data.get_buffer().copy()

            self.data = None

        try:
            bffer.pts = self.timestamp
        except ValueError as e:
            logger.error('%d' % self.timestamp)
            g_main_loop.quit()

        self.timestamp += bffer.duration

        return bffer

    def push_data(self, source):
        bff = self.copy_from_data() if self.isStream else self.build_white_black_stream(320, 240, 2)

        if bff is None:
            return True

        result  = source.emit('push-buffer', bff)
        logger.debug('pushed %s' % bff)

        if result != Gst.FlowReturn.OK:
            logger.debug('error on on_need_data: %s' % result)
            g_main_loop.quit()

        return True

    def on_enough_data(self, *args):
        logger.debug('enough data')
        if self.source_id:
            GObject.source_remove(self.source_id)
            self.source_id = None

if __name__ == '__main__':
    start=Main()
    logger.debug('start')
    g_main_loop.run()
