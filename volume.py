"""
Simple script that take an audio source and show its
channel levels using a GTK widget.
"""
import pygst
import gst
import gtk
import gtk.glade

from gui import GuiMixin

class VolumeWidget(GuiMixin):
    main_class = 'mainWindow'
    glade_file_path = 'volume-meter.glade'
    def __init__(self):
        self._build_gui()
        self._create_pipeline()

    def _create_pipeline(self):
        """Create a simple pipeline with an audio test source having a level
        and volume element
        """
        pipestr = 'audiotestsrc wave=ticks ! audioconvert ! level ! volume name=v ! pulsesink'
        self.pipeline = gst.parse_launch(pipestr)

        # get the bus and connect to it some callback
        # in order to get the levels
        bus = self.pipeline.get_bus()
        bus.enable_sync_message_emission()
        bus.add_signal_watch()
        bus.connect('message', self.on_message)

    def on_message(self, bus, message):
        t = message.type
        if t == gst.MESSAGE_ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            if self.on_eos:
                self.on_eos()
            self.playing = False
        elif t == gst.MESSAGE_EOS:
            if self.on_eos:
                self.on_eos()
            self.playing = False
        elif t == gst.MESSAGE_ELEMENT:
            message_name = message.structure.get_name()
            if message_name == "level":
                #import pdb;pdb.set_trace()
                print message.structure["peak"], message.structure["decay"]

    def play(self):
        self.playing = True
        gst.info("playing player")
        self.pipeline.set_state(gst.STATE_PLAYING)

        # set volume
        volume = self.pipeline.get_by_name('v')
        volume_value = volume.get_property('volume')
        self.builder.get_object('volumebutton').set_value(volume_value)


    def stop(self):
        self.pipeline.set_state(gst.STATE_NULL)
        gst.info("stopped player")
        self.playing = False


if __name__ == "__main__":
    gtk.gdk.threads_init()
    vw = VolumeWidget()
    vw.show_all()
    vw.play()
    gtk.main()
