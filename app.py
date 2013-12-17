from gi.repository import GObject, Gst
import sys
from sslog import logger

GObject.threads_init()
g_main_loop = GObject.MainLoop()
Gst.init(None)


class Main:
    def __init__(self, pipeline_string='videotestsrc ! tee name=t ! queue ! autovideosink t. ! queue ! appsink name=sink'):
        self.data = None# this will contain the data passed between
        self.source_id = None

        self.isWhite = False
        self.timestamp = 0

        self.pipeline = Gst.parse_launch(pipeline_string)

        self.appsink = self.pipeline.get_by_name('sink')

        assert self.appsink, 'appsink element named \'sink\' not found'


        self.pipeline.set_state(Gst.State.PLAYING)

        # OUTPUT pipeline
        self.pipeline_out = Gst.parse_launch('appsrc name=source ! videoconvert ! autovideosink')

        self.appsrc = self.pipeline_out.get_by_name('source')

        assert self.appsrc, 'appsrc element named \'source\' not found'

        self.appsrc.set_property('caps', Gst.Caps.from_string('video/x-raw,format=(string)RGB16,width=(int)384,height=(int)288,framerate=(fraction)1/1'))

        self.appsrc.connect('need-data', self.on_need_data)
        self.appsrc.connect('enough-data', self.on_enough_data)

        self.pipeline_out.set_state(Gst.State.PLAYING)

    def on_new_buffer(self, appsink):
        buffer = appsink.emit('pull-sample')
        self.data = buffer
        # logger.info('. %s' % buffer.get_caps().to_string())

    def on_need_data(self, source, *args):
        if not self.source_id:
            self.source_id = GObject.idle_add(self.push_data, source)

    def push_data(self, source):
        # http://gstreamer.freedesktop.org/data/doc/gstreamer/head/manual/html/section-data-spoof.html#section-spoof-appsrc
        size = 385 * 288 * 2;
        bffer = Gst.Buffer.new_allocate(None, size, None)
        bffer.memset(0, 0x00 if self.isWhite else 0xff, size)

        self.isWhite = not self.isWhite

        bffer.pts = self.timestamp
        bffer.duration = Gst.util_uint64_scale_int (1, Gst.SECOND, 2)

        self.timestamp += bffer.duration

        result  = source.emit('push-buffer', bffer)
        print result

        if result != Gst.FlowReturn.OK:
            logger.debug('error on on_need_data')
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
