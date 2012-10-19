import gobject
import gtk
import gst
import logging

# FIXME: globals are evils
stream = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

logger = logging.getLogger('miao')
logger.setLevel(logging.DEBUG)
logger.addHandler(stream)
stream.setFormatter(formatter)

class Pipeline(gobject.GObject):
    """Main class for multimedia handling.
    """
    __gsignals__ = {
        'error': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            (gobject.TYPE_FLOAT,)
        ),
    }
    def __init__(self, videodevicepaths, monitor_windows):
        """Initialize the Pipeline with the given device paths
        and with the windows to which will be played.

        the first monitor_windows will be the main monitor.
        """
        # some sanity checks
        assert len(videodevicepaths) + 1 == len(monitor_windows)

        self.videodevicepaths = videodevicepaths
        self.main_monitor_window = monitor_windows[0]
        self.monitor_windows = monitor_windows[1:]

        self._setup_pipeline()

    def _build_pipeline_string(self):
        """The final pipeline is in the form like

        v4l2src device=/dev/videoX ! queue ! tee name=t0 ! queue ! s.sink0 t0. ! queue ! autovideosink
        v4l2src device=/dev/videoX ! queue ! tee name=t1 ! queue ! s.sink1 t1. ! queue ! autovideosink
        ...
        input-selector name=s ! queue ! autovideosink

        where each video device has a tee that sends the stream to an autovideosink (that
        will be the monitor) and to an input-selector
        """
        count = 0
        pipes = []
        for devicepath in self.videodevicepaths:
            pipes.append(
                "v4l2src device=%s ! queue ! tee name=t%d ! queue ! s.sink%d t%d. ! queue ! autovideosink" % (
                    devicepath,
                    count,
                    count,
                    count
                )
            )
            count += 1

        pipes.append("input-selector name=s ! queue ! autovideosink")

        return " ".join(pipes)

    def _setup_pipeline(self):
        """Launch the pipeline and connect bus to the right signals"""
        self.pipeline_string = self._build_pipeline_string()
        logger.debug(self.pipeline_string)
        self.player = gst.parse_launch(self.pipeline_string)
        bus = self.player.get_bus()
        bus.enable_sync_message_emission()
        bus.add_signal_watch()

        bus.connect('sync-message::element', self.__cb_on_sync())
        bus.connect('message', self.__cb_factory())

        self.input_selector = self.player.get_by_name('s')

    def _get_monitor_from_imagesink(self, imagesink):
        """Return the gtk.gdk.Window instance associated with given imagesink"""
        import re
        index_search = re.search("autovideosink(\d+)-actual-sink-xvimage", imagesink)
        position = int(index_search.group(1)[0])
        if position < len(self.monitor_windows):
            return self.monitor_windows[position]
        else:
            return self.main_monitor_window

    def __cb_on_sync(self):
        """When an "on sync" message is emitted check if is
        a "prepare-xwindow-id" and if so assign the viewport
        to the correct autovideosink.

        Internally the name of the message's src attribute will be
        like "autovideosinkX-actual-sink-xvimage".
        """
        def on_sync_message(bus, message):
            if message.structure is None:
                return
            message_name = message.structure.get_name()
            #print '###', message_name

            """
            following this FAQ 

            http://faq.pygtk.org/index.py?file=faq20.006.htp&req=show

            we have to wrap code touching widgets
            with gtk.gdk.threads_enter() and gtk.gdk.threads_leave() otherwise
            errors like 

            python: ../../src/xcb_io.c:221: poll_for_event: asserzione "(((long) (event_sequence) - (long) (dpy->request)) <= 0)" non riuscita.

            will appear.
            """
            try:
                gtk.gdk.threads_enter()
                if message_name == "prepare-xwindow-id":
                    # Assign the viewport
                    imagesink = message.src
                    window = self._get_monitor_from_imagesink(imagesink.get_name())
                    window.set_sink(imagesink)
            finally:# this finally is helpful for avoid blocking crash
                gtk.gdk.threads_leave()

        return on_sync_message

    def __cb_factory(self):
        def _cb(bus, message):
            t = message.type
            if t == gst.MESSAGE_EOS:
                self.player.set_state(gst.STATE_NULL)
                self.status="PLAY"
            elif t == gst.MESSAGE_ERROR:
                err, debug = message.parse_error()
                print "Error: %s" % err, debug
                self.player.set_state(gst.STATE_NULL)
                self.status="PLAY"
        return _cb

    def play(self):
        self.player.set_state(gst.STATE_PLAYING)

    def switch_to(self, monitor):
        source_n = self.monitor_windows.index(monitor)
        padname = 'sink%d' % source_n
        logger.debug('switch to ' + padname)
        switch = self.player.get_by_name('s')
        stop_time = switch.emit('block')
        newpad = switch.get_static_pad(padname)
        start_time = newpad.get_property('running-time')

        gst.warning('stop time = %d' % (stop_time,))
        gst.warning('stop time = %s' % (gst.TIME_ARGS(stop_time),))

        gst.warning('start time = %d' % (start_time,))
        gst.warning('start time = %s' % (gst.TIME_ARGS(start_time),))

        gst.warning('switching from %r to %r'
                    % (switch.get_property('active-pad'), padname))
        switch.emit('switch', newpad, stop_time, start_time)