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

        self.pipeline = Gst.parse_launch(pipeline_string)

        self.appsink = self.pipeline.get_by_name('sink')

        assert self.appsink, 'appsink element named \'sink\' not found'

        self.appsink.connect('new-sample', self.on_new_buffer)
        self.appsink.set_property('emit-signals', True)

        self.pipeline.set_state(Gst.State.PLAYING)

        # OUTPUT pipeline
        self.pipeline_out = Gst.parse_launch('appsrc name=source ! autovideosink')

        self.appsrc = self.pipeline_out.get_by_name('source')

        assert self.appsrc, 'appsrc element named \'source\' not found'

        self.appsrc.connect('need-data', self.on_need_data)
        self.appsrc.connect('enough-data', self.on_enough_data)

        self.pipeline_out.set_state(Gst.State.PAUSED)

    def on_new_buffer(self, appsink):
        buffer = appsink.emit('pull-sample')
        self.data = buffer
        # logger.info('. %s' % buffer.get_caps().to_string())

    def on_need_data(self, source, *args):
        print args
        if not self.source_id:
            self.source_id = GObject.idle_add(self.push_data, source)

        self.pipeline_out.set_state(Gst.State.PLAYING)

    def push_data(self, source):
        if self.data:
            print '.',
            source.emit('push-buffer', self.data.get_buffer())

        return True

    def on_enough_data(self, *args):
        if self.source_id:
            GObject.source_remove(self.source_id)
            self.source_id = None

if __name__ == '__main__':
    start=Main()
    logger.debug('start')
    g_main_loop.run()
