"""
Simple script that take an audio source and show its
channel levels using a GTK widget.

For RMS/Peak/Decay configuration
    http://q-syshelp.qschome.com/Content/Schematic%20Library/meter2.htm
"""
from gi.repository import Gst, Gtk
import math

from gui import GuiMixin

class VolumeWidget(GuiMixin):
    main_class = 'mainWindow'
    glade_file_path = 'volume-meter.glade'

    def __init__(self, audio_element=None):
        self._build_gui()

        self.gui_volume = self.builder.get_object('volumebutton')
        self.gui_level = self.builder.get_object('progressbar')

        self._create_pipeline()

        # set volume
        volume = self.pipeline.get_by_name('v')
        self.set_gui_volume(volume.get_property('volume'))

        self.level = self.pipeline.get_by_name('l')

    def _create_pipeline(self):
        """Create a simple pipeline with an audio test source having a level
        and volume element
        """
        pipestr = 'pulsesrc ! audioconvert ! level name=l ! volume name=v ! pulsesink'
        self.pipeline = Gst.parse_launch(pipestr)

        # get the bus and connect to it some callback
        # in order to get the levels
        bus = self.pipeline.get_bus()
        bus.enable_sync_message_emission()
        bus.add_signal_watch()
        bus.connect('message', self.on_message)

    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print "Error: %s" % err, debug
            if self.on_eos:
                self.on_eos()
            self.playing = False
        elif t == Gst.MessageType.EOS:
            if self.on_eos:
                self.on_eos()
            self.playing = False
        elif t == Gst.MessageType.ELEMENT:
            message_name = message.get_structure().get_name()
            if message_name == "level":
                rms = message.get_structure().get_value('rms')[0]
                peak = message.get_structure().get_value('peak')[0]
                decay = message.get_structure().get_value('decay')[0]
                print rms, peak, decay
                self.set_gui_level(self._rescale_db_to_level(rms))

    def _rescale_db_to_level(self, db_value):
        """Since the level is from 0 to 100 but the db levels are(?) in the
        range -100 to 20, we use this function to shift and rescale

        0/-100 : 100/20
        """
        db_min    = -100.0
        db_max    = 20.0
        level_min = 0.0
        level_max = 100.0

        v = level_min + abs(db_value) / (db_max - db_min) * (level_max - level_min)

        print '###', db_value, v

        return v

    def set_gui_volume(self, volume_level):
        self.gui_volume.set_value(volume_level)

    def set_gui_level(self, value):
        self.gui_level.set_value(value)

    def play(self):
        self.playing = True
        #Gst.info("playing player")
        self.pipeline.set_state(Gst.State.PLAYING)


    def stop(self):
        self.pipeline.set_state(Gst.State.NULL)
        #gst.info("stopped player")
        self.playing = False

    def _on_action_quit(self, action):
        self.stop()
        Gtk.main_quit()


if __name__ == "__main__":
    Gst.init(None)
    vw = VolumeWidget()
    vw.show_all()
    vw.play()
    Gtk.main()
