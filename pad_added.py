#!/usr/bin/python
"""
Original code from <http://www.jonobacon.org/2006/11/03/gstreamer-dynamic-pads-explained/>
adapted for version 1.0 of GStreamer.
"""

from gi.repository import GObject, Gst
import sys
from sslog import logger

GObject.threads_init()
g_main_loop = GObject.MainLoop()
Gst.init(None)


class Main:
    def __init__(self, location):
        self.pipeline = Gst.Pipeline()

        self.filesrc = Gst.ElementFactory.make("filesrc", None)
        self.pipeline.add(self.filesrc)
        self.filesrc.set_property("location", location)

        self.decode = Gst.ElementFactory.make("decodebin", "decode")
        self.decode.connect("pad-added", self.OnDynamicPad)
        self.pipeline.add(self.decode)

        self.filesrc.link(self.decode)

        self.convert = Gst.ElementFactory.make("audioconvert", "convert")
        self.pipeline.add(self.convert)

        self.sink = Gst.ElementFactory.make("autoaudiosink", "sink")
        self.pipeline.add(self.sink)

        self.convert.link(self.sink)

        self.videosink = Gst.ElementFactory.make("autovideosink", "imagesink")
        self.pipeline.add(self.videosink)

        self.bus = self.pipeline.get_bus()
        self.bus.enable_sync_message_emission()
        self.bus.add_signal_watch()

        def __on_message(bus, message):
            t = message.type
            logger.info('received message type \'%s\' from \'%s\'' % (
                t.first_value_nick, message.src.get_name(),
            ))
            if t == Gst.MessageType.EOS:
                self.player.set_state(Gst.State.NULL)
            elif t == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                print err, debug
                g_main_loop.quit()

        self.bus.connect('message', __on_message)

        self.pipeline.set_state(Gst.State.PLAYING)

    def OnDynamicPad(self, dbin, pad):
        logger.debug("OnDynamicPad Called! %s %s" % (dbin.get_name(), pad,))
        caps = pad.query_caps(None)

        logger.debug(' with capabilities: %s' % caps.to_string())

        if caps.to_string().startswith('audio'):
            pad.link(self.convert.get_static_pad('sink'))
        elif caps.to_string().startswith('video'):
            pad.link(self.videosink.get_static_pad('sink'))


start=Main(sys.argv[1])
g_main_loop.run()
