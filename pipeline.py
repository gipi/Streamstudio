"""
Main class to manage gstreamer pipeline construction.

It simply attempts to build a pipeline with N sources and associated monitors (one for each source)
and one only output. The source that will be sent to the final sink will be decided by an input-selector
at runtime.

Sources can be also added at runtime.

All of this can be executed from a python terminal like the following session

    >>> p = Pipeline(["/dev/video0", "/dev/video1"])
    >>> gobject.threads_init()
    >>> p.play()

(gobject.threads_init() is mandatory otherwise a segfault will happen).

After this three little windows pop up; you can switch between them using the switch_to() function

    >>> p.switch_to("/dev/video1")

If you ask for a switch to an unexisting source an AttributeError will be thrown.

The Pipeline class has two signals associated with it

 - set-sink: when the autovideosink looks for an xwindow output the instance ask if someone
             want to be a sink (if no one responds then open a default window)

 - error: some errors happened
"""
import gobject
import gst
import glib
import os
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
    def __init__(self, videodevicepaths, main_monitor_name="main_monitor", xsink_cb=None):
        """Initialize the Pipeline with the given device paths
        and with the windows to which will be played.

        If xsink_cb is passed then will be used instead of the 'set-sink' signal
        in order to set the prepare-xwindow-id
        """
        gobject.GObject.__init__(self)

        self.videodevicepaths = videodevicepaths
        self.main_monitor_name = main_monitor_name
        self.xsink_cb = xsink_cb

        # this will maintain an unique identifier for the input-selector sink
        # since we want to add/remove the number must be unique so increment only
        self.source_counter = 0
        # self.sources has a key the video device paths and as value another dictionary
        # indicating with the key 'sink' the id of the sink corresponding to the
        # input-selector's sink associated. Also an 'element' key is present, it contains
        # all the elements associated to this source.
        self.sources = {}

        self._setup_pipeline()

    def _add_source(self, devicepath, elements=None):
        """Add the given source to the internal dictionary.

        The dictionary uses as key the devicepath and as value another
        dictionary with the id in the 'sink' key and a list of elements
        in the key named 'elements'.
        """
        self.sources[devicepath] = {
            'sink': self.source_counter,
            'elements': elements,
        }

        self.source_counter += 1

    def _build_pipeline_string(self):
        """The final pipeline is in the form like

        videotestsrc               ! tee name=t0 ! queue ! s.sink0 t0. ! queue ! autovideosink
        v4l2src device=/dev/videoX ! tee name=t1 ! queue ! s.sink1 t1. ! queue ! autovideosink
        ...
        input-selector name=s ! queue ! autovideosink

        where each video device has a tee that sends the stream to an autovideosink (that
        will be the monitor) and to an input-selector
        """
        pipes = []
        pipes.append("videotestsrc ! tee name=t%d ! queue ! s.sink%d t%d. ! queue ! xvimagesink name=fakesrc" % (
            self.source_counter,
            self.source_counter,
            self.source_counter,
        ))

        self._add_source("fake")

        return " ".join(pipes) + " input-selector name=s ! queue ! xvimagesink name=%s" % self.main_monitor_name

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
        # TODO: create the videotestsrc piece of pipeline programmatically
        #       so to have special cases
        self.sources["fake"]["elements"] = [self.player.get_by_name("fakesrc"),]

    def __cb_on_sync(self):
        """When an "on sync" message is emitted check if is
        a "prepare-xwindow-id" and if so assign the viewport
        to the correct autovideosink.

        Internally the name of the message's src attribute will be
        like "<name>-actual-sink-xvimage" where <name> is like autovideosink0
        for the default.

        If to the constructor was passed the 'xsink_cb' then it will be called.
        """
        def on_sync_message(bus, message):
            if message.structure is None:
                return
            message_name = message.structure.get_name()
            if message_name == "prepare-xwindow-id":
                imagesink = message.src
                devicepath = None
                # find out which device sends the message
                for dpath, value in self.sources.iteritems():
                    if value['elements'] and imagesink in value['elements']:
                        devicepath = dpath
                        break

                if self.xsink_cb:
                    self.xsink_cb(imagesink, devicepath)
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

                self.emit("error", err)

                self.remove_source(message.src.get_name())
        return _cb

    def play(self):
        """Set the internal gstreamer pipeline to STATE_PLAYING"""
        self.player.set_state(gst.STATE_PLAYING)

    def kill(self):
        self.player.set_state(gst.STATE_PAUSED)
        self.player.set_state(gst.STATE_NULL)

    def switch_to(self, devicepath):
        """Select the device path passed as argument as source for the output"""
        try:
            source_n = self.sources[devicepath]["sink"]
        except KeyError, e:
            logger.exception(e)
            raise AttributeError("source '%s' doesn't exist, add it before to launch this" % (devicepath,))

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
        """Add a source to this pipeline and connect to the
        input-selector.

        If "name" is passed will be used internally as reference.
        """
        # check that the argument exists
        try:
            os.stat(devicepath)
        except OSError:
            raise AttributeError("source '%s' doesn't exist" % devicepath)
        if devicepath in self.videodevicepaths:
            raise AttributeError("device '%s' is yet a source" % devicepath)
        # first create all the elements
        video_source = gst.element_factory_make("v4l2src")
        video_source.set_property("device", devicepath)
        video_source.set_property("name", devicepath)

        imagesink = gst.element_factory_make("xvimagesink")

        queue2 = gst.element_factory_make("queue")
        queue3 = gst.element_factory_make("queue")

        tee = gst.element_factory_make("tee", "t%d" % self.source_counter)

        # stop the pipeline
        self.player.set_state(gst.STATE_PAUSED)

        # add the elements to the pipeline
        self.player.add(video_source, queue2, queue3, imagesink, tee)

        # link them correctly to the first free sink of the input-selector
        gst.element_link_many(video_source, tee, queue2)
        # set the sink to the last value free in source_counter
        # otherwise input-selector reuse them
        queue2.link_pads(None, self.input_selector, 'sink%d' % self.source_counter)
        # finally link a src of the tee to the imagesink
        gst.element_link_many(tee, queue3, imagesink)

        # restart the pipeline
        self.player.set_state(gst.STATE_PLAYING)

        # update the number of sources
        self.videodevicepaths.append(devicepath)
        # update the sources
        self._add_source(
            devicepath, [
                queue2,
                queue3,
                tee,
                imagesink
            ])

    def remove_source(self, devicepath):
        """Remove a source by name"""
        if devicepath not in self.videodevicepaths:
            raise AttributeError("'%s' is not a source" % devicepath)

        _source = self.sources[devicepath]

        source_element = self.player.get_by_name(devicepath)

        elements_to_remove = _source['elements']
        # "pad block on the wrong pad, block src pads in push mode and sink pads in pull mode."+
        # the first element is the queue linked with input-selector
        queue_to_unlink = elements_to_remove.pop(0)
        # When the pipeline is stalled, for example in PAUSED, this can take
        # an indeterminate amount of time. You can pass None as the callback 
        # to make this call block. Be careful with this blocking call as it
        # might not return for reasons stated above.
        queue_to_unlink.get_pad("src").set_blocked(True)
        source_element.get_pad("src").set_blocked(True)

        self.player.set_state(gst.STATE_PAUSED)
        source_element.unlink(queue_to_unlink)
        source_element.set_state(gst.STATE_NULL)
        self.player.remove(source_element)

        queue_to_unlink.set_state(gst.STATE_NULL)
        queue_to_unlink.unlink(self.input_selector)
        self.player.remove(queue_to_unlink)
        # add source to the list of element to remove
        elements_to_remove.insert(0, source_element)

        elements_to_remove.pop().set_state(gst.STATE_NULL)

        logger.debug('will be removed %s' % elements_to_remove)
        for element in elements_to_remove:
            # STATE_NULL allow to garbage collect the element
            element.set_state(gst.STATE_NULL)
            self.player.remove(element)

        self.sources.pop(devicepath)
        self.videodevicepaths.remove(devicepath)

        self.player.set_state(gst.STATE_PLAYING)


if __name__ == "__main__":
    import sys
    gobject.threads_init()
    p = Pipeline([])
    for source in sys.argv[1:]:
        p.add_source(source)
    p.play()
    loop = glib.MainLoop()
    loop.run()
