#!/usr/bin/python
"""
Original code from <http://www.jonobacon.org/2006/11/03/gstreamer-dynamic-pads-explained/>
adapted for version 1.0 of GStreamer.
"""

from gi.repository import GObject, Gst, Gtk
import sys

GObject.threads_init()
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

        self.videosink = Gst.ElementFactory.make("xvimagesink", "imagesink")
        self.pipeline.add(self.videosink)

        self.bus = self.pipeline.get_bus()
        self.bus.enable_sync_message_emission()
        self.bus.add_signal_watch()

        def __on_message(bus, message):
            t = message.type
            print t
            if t == Gst.MessageType.EOS:
                self.player.set_state(Gst.State.NULL)
            elif t == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                print err, debug
                Gtk.main_quit()

        self.bus.connect('message', __on_message)

        self.pipeline.set_state(Gst.State.PLAYING)

    def OnDynamicPad(self, dbin, pad):
        caps = pad.get_current_caps().to_string()
        print "OnDynamicPad Called!", dbin, pad, caps
        if caps.startswith('audio'):
            pad.link(self.convert.get_static_pad('sink'))
        elif caps.startswith('video'):
            pad.link(self.videosink.get_static_pad('sink'))


start=Main(sys.argv[1])
Gtk.main()
