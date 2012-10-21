"""
Main class to manage gstreamer pipeline construction.

It simply attempts to build a pipeline with N sources and associated monitors (one for each source)
and one only output. The source that will be sent to the final sink will be decided by an input-selector
at runtime.

Sources can be also added at runtime.

All of this can be executed from a python terminal like the following session

    >>> p = Pipeline(["/dev/video0", "/dev/video1"])
    >>> p.play()

After this three little windows pop up; you can switch between them using the switch_to() function
(remember that the list of devices are 0-indexed).

    >>> p.switch_to(1)

If you ask for a switch to an unexisting source an AttributeError will be thrown.

The Pipeline class has two signal associated with it

 - set-sink: when the autovideosink looks for an xwindow output the instance ask if someone
             want to be a sink (if no one responds then open a default window)

 - error: some errors happened
"""
import gobject
import gtk
import gst
from sslog import logger


class Pipeline(gobject.GObject):
    """Main class for multimedia handling.
    """
    __gsignals__ = {
        'error': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            (gobject.TYPE_STRING,)
        ),
        # TODO: set-sink -> sink-request
        'set-sink': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            (gobject.TYPE_OBJECT,)
        )
    }
    def __init__(self, videodevicepaths, main_monitor_name="main_monitor"):
        """Initialize the Pipeline with the given device paths
        and with the windows to which will be played.

        the first monitor_windows will be the main monitor.
        """
        gobject.GObject.__init__(self)

        self.videodevicepaths = videodevicepaths
        self.main_monitor_name = main_monitor_name

        # this will maintain an unique identifier for the input-selector sink
        self.source_counter = 0

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
        pipes = []
        pipes.append("input-selector name=s ! queue ! autovideosink name=%s sync=false" % self.main_monitor_name)
        for devicepath in self.videodevicepaths:
            pipes.append(
                "v4l2src device=%s ! queue ! tee name=t%d ! queue ! s.sink%d t%d. ! queue ! autovideosink" % (
                    devicepath,
                    self.source_counter,
                    self.source_counter,
                    self.source_counter
                )
            )
            self.source_counter += 1


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

    def __cb_on_sync(self):
        """When an "on sync" message is emitted check if is
        a "prepare-xwindow-id" and if so assign the viewport
        to the correct autovideosink.

        Internally the name of the message's src attribute will be
        like "<name>-actual-sink-xvimage" where <name> is like autovideosink0
        for the default.
        """
        def on_sync_message(bus, message):
            if message.structure is None:
                return
            message_name = message.structure.get_name()
            if message_name == "prepare-xwindow-id":
                imagesink = message.src
                self.emit("set-sink", imagesink)

        return on_sync_message

    def __cb_factory(self):
        def _cb(bus, message):
            t = message.type
            if t == gst.MESSAGE_EOS:
                self.player.set_state(gst.STATE_NULL)
            elif t == gst.MESSAGE_ERROR:
                # TODO: remove element if is a source
                #and retry to restart the pipeline
                err, debug = message.parse_error()
                logger.error("fatal from '%s'" % message.src.get_name())
                logger.error("%s:%s" % (err, debug))
                self.player.set_state(gst.STATE_NULL)
                self.emit("error", err)
        return _cb

    def play(self):
        gobject.threads_init()
        gtk.gdk.threads_init()
        self.player.set_state(gst.STATE_PLAYING)

    def switch_to(self, monitor_idx):
        source_n = monitor_idx
        n_sources = len(self.videodevicepaths)
        if monitor_idx > n_sources:
            raise AttributeError("there are only %d source%s" % (n_sources, "s" if n_sources > 1 else ""))
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

    def add_source(self, devicepath):
        """Add a new videosrc and connect to the input-selector"""
        n_actual_sink = len(self.videodevicepaths)

        # first create all the elements
        video_source = gst.element_factory_make("v4l2src")
        video_source.set_property("device", devicepath)

        imagesink = gst.element_factory_make("autovideosink")

        queue1 = gst.element_factory_make("queue")
        queue2 = gst.element_factory_make("queue")
        queue3 = gst.element_factory_make("queue")

        tee = gst.element_factory_make("tee", "t%d" % n_actual_sink)

        # stop the pipeline
        self.player.set_state(gst.STATE_PAUSED)

        # add the elements to the pipeline
        self.player.add(video_source, queue1, queue2, queue3, imagesink, tee)

        # link them correctly to the first free sink of the input-selector
        gst.element_link_many(video_source, queue1, tee, queue2, self.input_selector)
        gst.element_link_many(tee, queue3, imagesink)

        # restart the pipeline
        self.player.set_state(gst.STATE_PLAYING)

        # update the number of sources
        self.videodevicepaths.append(devicepath)
