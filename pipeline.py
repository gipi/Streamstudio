#!/usr/bin/env python
"""
Main class to manage gstreamer pipelines construction.

    >>> p = Pipeline()
    >>> gobject.threads_init()
    >>> p.play()

(GObject.threads_init() is mandatory otherwise a segfault will happen).

After this three little windows pop up; you can switch between them using the switch_to() function

The BasePipeline class has two signals associated with it

 - set-sink: when the autovideosink looks for an xwindow output the instance ask if someone
             want to be a sink (if no one responds then open a default window)

 - error: some errors happened
"""
import os
from sslog import logger
from gi.repository import Gst, GObject

print 'GObject v%s' % GObject._version
print 'PyGObject v%s' % (
    '.'.join([str(x) for x in GObject.pygobject_version]),
)

import gi
gi.require_version('Gst', '1.0')

import platform; print 'python', platform.python_version()
print Gst.version_string()



class BasePipeline(GObject.GObject):
    """Base class to manage GStreamer pipelines"""
    __gsignals__ = {
        'error': (
            GObject.SIGNAL_RUN_LAST,
            GObject.TYPE_NONE,
            (GObject.TYPE_STRING,)
        ),
        # TODO: set-sink -> sink-request
        'set-sink': (
            GObject.SIGNAL_RUN_LAST,
            GObject.TYPE_NONE,
            (GObject.TYPE_OBJECT,)
        )
    }
    def __init__(self, pipeline_string):
        import sys
        Gst.init_check(sys.argv)
        GObject.GObject.__init__(self)

        self.pipeline_string = pipeline_string

        self._setup_pipeline()

    def _setup_bus(self):
        bus = self.player.get_bus()
        bus.enable_sync_message_emission()
        bus.add_signal_watch()

        bus.connect('sync-message::element', self.__cb_on_sync())
        bus.connect('message', self.__cb_factory())

    def _setup_pipeline(self):
        """Launch the pipeline and connect bus to the right signals"""
        logger.debug(self.pipeline_string)
        self.player = Gst.parse_launch(self.pipeline_string)

        self._setup_bus()

    def _on_message_error(self, message):
        # TODO: remove element if is a source
        #and retry to restart the pipeline
        err, debug = message.parse_error()
        logger.error("fatal from '%s'" % message.src.get_name())
        logger.error("%s:%s" % (err, debug))

        self.emit("error", err)


    def _on_message_prepare_window_handle(self, message):
        imagesink = message.src
        self.emit("set-sink", imagesink)

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
            t = message.type
            if message.get_structure() is None:
                return

            message_name = message.get_structure().get_name()

            logger.debug('sync: received message type \'%s\' with name \'%s\' from \'%s\'' % (
                t.first_value_nick, message_name, message.src.get_name(),
            ))

            if message_name == "prepare-window-handle":
                self._on_message_prepare_window_handle(message)

        return on_sync_message

    def __cb_factory(self):
        def _cb(bus, message):
            t = message.type
            src = message.src
            logger.debug('received message type \'%s\' from \'%s\'' % (
                t.first_value_nick, src.get_name(),
            ))

            if t == Gst.MessageType.EOS:
                self.player.set_state(Gst.State.NULL)
            elif t == Gst.MessageType.WARNING:
                logger.debug(' %s' % (message.parse_warning(),))
            elif t == Gst.MessageType.QOS:
                logger.debug(' %s' % (message.parse_qos(),))
            elif t == Gst.MessageType.STREAM_STATUS:
                logger.debug(' %s' % (message.parse_stream_status(),))
            elif t == Gst.MessageType.STATE_CHANGED:
                old_state, new_state, pending = message.parse_state_changed()
                logger.debug(' %s -> %s (pending %s)' %
                    (old_state.value_nick, new_state.value_nick, pending.value_nick,)
                )
            elif t == Gst.MessageType.ERROR:
                self._on_message_error(message)
        return _cb

    def pause(self):
        """Set the internal gstreamer pipeline to STATE_PAUSED"""
        self.player.set_state(Gst.State.PAUSED)

    def play(self):
        """Set the internal gstreamer pipeline to STATE_PLAYING"""
        self.player.set_state(Gst.State.PLAYING)

    def kill(self):
        self.player.set_state(Gst.State.PAUSED)
        self.player.set_state(Gst.State.NULL)

    def get_position(self):
        return self.player.query_position(Gst.Format.TIME)[1]

    def get_duration(self):
        return self.player.query_duration(Gst.Format.TIME)[1]


class Pipeline(BasePipeline):
    """Main class for multimedia handling.
    """
    def __init__(self, main_monitor_name="main_monitor", xsink_cb=None):
        """Initialize the Pipeline with the given device paths
        and with the windows to which will be played.

        If xsink_cb is passed then will be used instead of the 'set-sink' signal
        in order to set the prepare-xwindow-id
        """

        self.videodevicepaths = []
        self.main_monitor_name = main_monitor_name
        self.xsink_cb = xsink_cb

        # this will maintain an unique identifier for the input-selector sink
        # since we want to add/remove the number must be unique so increment only
        self.source_counter = 0
        self.source_counter_audio = 0
        self.demux_counter = 0
        # self.sources has a key the video device paths and as value another dictionary
        # indicating with the key 'sink' the id of the sink corresponding to the
        # input-selector's sink associated. Also an 'element' key is present, it contains
        # all the elements associated to this source.
        self.sources = {}

        super(Pipeline, self).__init__(self._build_pipeline_string())

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
        self.source_counter_audio += 1

    def _build_pipeline_string(self):
        """The final pipeline is in the form like

        videotestsrc               ! tee name=t0 ! queue ! s.sink0 t0. ! queue ! autovideosink
        v4l2src device=/dev/videoX ! tee name=t1 ! queue ! s.sink1 t1. ! queue ! autovideosink
        ...
        input-selector name=s ! queue ! autovideosink

        where each video device has a tee that sends the stream to an autovideosink (that
        will be the monitor) and to an input-selector

        Also an audio pipeline is added

        audiotestsrc wave=8 ! tee name=ta0 ! queue ! sa.sink0
         ...
        input-selector name=sa ! autoaudiosink
        """
        self._add_source("fake")

        return 'videotestsrc ! video/x-raw,framerate=1/5 ! queue ! tee name=t0 ! input-selector name=s ! queue ! xvimagesink name=main_monitor sync=false t0. ! xvimagesink name=fakesrc sync=false audiotestsrc wave=8 ! queue ! tee name=ta0 ! input-selector name=sa ! queue ! autoaudiosink'

    def _setup_pipeline(self):
        super(Pipeline, self)._setup_pipeline()

        self.input_selector = self.player.get_by_name('s')
        self.input_selector_audio = self.player.get_by_name('sa')
        # TODO: create the videotestsrc piece of pipeline programmatically
        #       so to have special cases
        self.sources["fake"]["elements"] = [self.player.get_by_name("fakesrc"),]

    def _on_message_prepare_window_handle(self, message):
        imagesink = message.src
        devicepath = None
        # find out which device sends the message
        for dpath, value in self.sources.iteritems():
            if value['elements'] and imagesink in value['elements']:
                devicepath = dpath
                break

        if self.xsink_cb:
            self.xsink_cb(imagesink, devicepath)

        super(Pipeline, self)._on_message_prepare_window_handle(message)

    def switch_to(self, devicepath):
        """Select the device path passed as argument as source for the output"""
        try:
            source_n = self.sources[devicepath]["sink"]
        except KeyError, e:
            logger.exception(e)
            raise AttributeError("source '%s' doesn't exist, add it before to launch this" % (devicepath,))

        padname = 'sink_%d' % source_n
        logger.debug('switch to ' + padname)
        switch = self.player.get_by_name('s')
        newpad = switch.get_static_pad(padname)
        start_time = newpad.get_property('running-time')



        logger.info('switching from %r to %r'
                    % (switch.get_property('active-pad'), padname))

        switch.set_property("active-pad", newpad)

    def _add_audio_branch_to_pipeline(self, src, sink):
        self.source_counter_audio += 1
        return self._add_branch_to_pipeline(
            self.input_selector_audio,
            src,
            sink,
            "ta%d" % self.source_counter_audio,
            'sink_%d' % self.source_counter_audio)

    def _add_video_pad_to_pipeline(self, src_pad):
        imagesink = Gst.ElementFactory.make("xvimagesink", None)
        # sink=False otherwise all is hanging
        imagesink.set_property("sync", False)

        return self._connect_pad_to_pipeline(
            self.input_selector,
            src_pad,
            imagesink,
            "t%d" % self.source_counter,
            'sink_%d' % self.source_counter)

    def _add_video_branch_to_pipeline(self, src):
        imagesink = Gst.ElementFactory.make("xvimagesink", None)
        # sink=False otherwise all is hanging
        imagesink.set_property("sync", False)

        return self._add_branch_to_pipeline(
            self.input_selector,
            src,
            imagesink,
            "t%d" % self.source_counter,
            'sink_%d' % self.source_counter)

    def _connect_pad_to_pipeline(self, input_selector, src_pad, sink, tee_name, sink_name):
        queue2 = Gst.ElementFactory.make("queue", None)
        queue3 = Gst.ElementFactory.make("queue", None)

        tee = Gst.ElementFactory.make("tee", tee_name)

        # stop the pipeline
        self.player.set_state(Gst.State.PAUSED)

        # add the elements to the pipeline
        self.player.add(queue2)
        self.player.add(queue3)
        self.player.add(sink)
        self.player.add(tee)

        # link them correctly to the first free sink of the input-selector
        # use the last src_elements element
        src_pad.link(tee.get_static_pad('sink'))
        tee.link(queue2)

        # set the sink to the last value free in source_counter
        # otherwise input-selector reuse them
        queue2.link_pads(None, input_selector, sink_name)
        # finally link a src of the tee to the imagesink
        tee.link(queue3)
        queue3.link(sink)

        # restart the pipeline
        self.player.set_state(Gst.State.PLAYING)

        return [queue2, queue3, tee, sink]

    def _add_branch_to_pipeline(self, input_selector, src, sink, tee_name, sink_name):
        """
        Create a branch to connect to the given input_selector.

        src must be already be added to the pipeline.
        """
        queue2 = Gst.ElementFactory.make("queue", None)
        queue3 = Gst.ElementFactory.make("queue", None)

        tee = Gst.ElementFactory.make("tee", tee_name)

        # stop the pipeline
        self.player.set_state(Gst.State.PAUSED)

        # add the elements to the pipeline
        self.player.add(queue2)
        self.player.add(queue3)
        self.player.add(sink)
        self.player.add(tee)

        # link them correctly to the first free sink of the input-selector
        # use the last src_elements element
        src.link(tee)
        tee.link(queue2)

        # set the sink to the last value free in source_counter
        # otherwise input-selector reuse them
        queue2.link_pads(None, input_selector, sink_name)
        # finally link a src of the tee to the imagesink
        tee.link(queue3)
        queue3.link(sink)

        # restart the pipeline
        self.player.set_state(Gst.State.PLAYING)

        return [queue2, queue3, tee, sink]

    def _check_source(self, location):
        # check that the argument exists
        try:
            os.stat(location)
        except OSError:
            raise AttributeError("source '%s' doesn't exist" % location)

        if location in self.videodevicepaths:
            raise AttributeError("device '%s' is yet a source" % location)

    def add_source_device(self, devicepath):
        """Add a source to this pipeline and connect to the
        input-selector.

        If "name" is passed will be used internally as reference.
        """
        self._check_source(devicepath)
        # first create all the elements
        video_source = Gst.ElementFactory.make("v4l2src", None)
        video_source.set_property("device", devicepath)
        video_source.set_property("name", devicepath)

        self.player.add(video_source)

        elements_added = self._add_video_branch_to_pipeline(video_source)

        # update the number of sources
        self.videodevicepaths.append(devicepath)
        # update the sources
        self._add_source(devicepath, elements_added)

    def add_source_file(self, location):
        """Try to add as source a given file at location passed as argument.

        Since it uses the decodebin element, the pad adding is asynchronous.
        """
        self._check_source(location)

        filesrc = Gst.ElementFactory.make('filesrc', None)
        filesrc.set_property('location', location)

        decodebin_name = 'demux%d' % self.demux_counter
        decodebin = Gst.ElementFactory.make('decodebin', decodebin_name)

        self.player.set_state(Gst.State.PAUSED)

        self.player.add(decodebin)
        self.player.add(filesrc)

        filesrc.link(decodebin)

        def on_pad_added(element, pad):
            caps = pad.get_current_caps().to_string()
            logger.info('pad \'%s\',  with caps \'%s\', added from element \'%s\'' % (
                pad.get_name(), caps, element.get_name(),
            ))
            if caps.startswith('video'):
                elements_added = self._add_video_pad_to_pipeline(pad)
                self._add_source(location, elements_added)

        decodebin.connect('pad-added', on_pad_added)

        self.player.set_state(Gst.State.PLAYING)

        self.demux_counter += 1

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

        self.player.set_state(Gst.State.PAUSED)
        source_element.unlink(queue_to_unlink)
        source_element.set_state(Gst.State.NULL)
        self.player.remove(source_element)

        queue_to_unlink.set_state(Gst.State.NULL)
        queue_to_unlink.unlink(self.input_selector)
        self.player.remove(queue_to_unlink)
        # add source to the list of element to remove
        elements_to_remove.insert(0, source_element)

        elements_to_remove.pop().set_state(Gst.State.NULL)

        logger.debug('will be removed %s' % elements_to_remove)
        for element in elements_to_remove:
            # STATE_NULL allow to garbage collect the element
            element.set_state(Gst.STATE_NULL)
            self.player.remove(element)

        self.sources.pop(devicepath)
        self.videodevicepaths.remove(devicepath)

        self.player.set_state(Gst.State.PLAYING)

def _quote_spaces(location):
    return location.replace(' ', '\ ').replace('(', '\(').replace(')', '\)')

class PadPipeline(BasePipeline):
    """This pipeline use internally decodebin to create at runtime
    the needed pads
    """
    __gsignals__ = {
        'stream-added': (
            GObject.SIGNAL_RUN_LAST,
            GObject.TYPE_NONE,
            (GObject.TYPE_STRING,)
        ),
    }
    def __init__(self, location):
        super(PadPipeline, self).__init__(
            # FIXME: create element on pad-added signal when necessary, otherwise we are limited to only one audio and video sink
            'filesrc location=%s ! decodebin name=demux' % (
                _quote_spaces(location),
            )
        )

    def _setup_pipeline(self):
        super(PadPipeline, self)._setup_pipeline()

        # TODO: use '_X' for element intended to not be public
        self.decode = self.player.get_by_name('demux')
        self.video_queue = self.player.get_by_name('video_queue')
        self.audio_queue = self.player.get_by_name('audio_queue')
        self.audiosink = self.player.get_by_name('audiosink')

        self.decode.connect("pad-added", self._on_dynamic_pad)

        #self.player.set_state(Gst.State.PAUSED)

    def _on_dynamic_pad(self, dbin, pad):
        caps = pad.query_caps(None).to_string()
        logger.debug('dynamic pad with caps %s' % caps)

        if caps.startswith('audio'):
            self._on_audio_dynamic_pad(dbin, pad)
        elif caps.startswith('video'):
            self._on_video_dynamic_pad(dbin, pad)


    def _on_video_dynamic_pad(self, dbin, pad):
        logger.debug('video pad detected')
 
        videosink = Gst.ElementFactory.make('autovideosink', None)

        self.player.add(videosink)
        # http://delog.wordpress.com/2011/07/25/link-dynamic-pads-of-demuxer/
        #  The state of these new elements needs to set to GST_STATE_PLAYING.
        videosink.set_state(Gst.State.PLAYING)

        pad.link(videosink.get_static_pad('sink'))

        self.emit('stream-added', 'video')

    def _on_audio_dynamic_pad(self, dbin, pad):
        logger.debug('audio pad detected')

        audiosink = Gst.ElementFactory.make('autoaudiosink', None)
        audioconvert = Gst.ElementFactory.make('audioconvert', None)

        self.player.add(audiosink)
        self.player.add(audioconvert)

        audiosink.set_state(Gst.State.PLAYING)
        audioconvert.set_state(Gst.State.PLAYING)

        audioconvert.link(audiosink)
        pad.link(audioconvert.get_static_pad('sink'))

        self.emit('stream-added', 'audio')


import cmd

class PipelineShell(cmd.Cmd):
    def __init__(self):
        cmd.Cmd.__init__(self)
        self.prompt = "\033[1;31mstreamstudio> \033[0m"
        self.p = Pipeline()
        GObject.threads_init()
        #l = GObject.MainLoop()
        #l.run()

    def do_EOF(self, line):
        return True

    def emptyline(self):
        return ''

    def do_add(self, line):
        """Add a source"""
        if line == "":
            return

        try:
            self.p.add_source_device(line)
        except AttributeError as e:
            print e.message

    def do_add_file(self, line):
        if line == '':
            return

        try:
            self.p.add_source_file(line)
        except AttributeError as e:
            print e.message

    def do_remove(self, line):
        """Remove a source, pass a device path as argument"""
        if line == "":
            return

        try:
            self.p.remove_source(line)
        except AttributeError as e:
            print e.message

    def do_play(self, line):
        self.p.play()

    def do_switch(self, line):
        try:
            self.p.switch_to(line)
        except AttributeError as e:
            print e.message


if __name__ == "__main__":
    import sys
    g_main_loop = GObject.MainLoop()
    GObject.threads_init()
    Gst.init(None)

    p = PadPipeline(sys.argv[1])
    def _on_error(*args):
        g_main_loop.quit()

    def _on_source_added(*args):
        print args
        logger.info('added %s' % args[1])

    p.connect('error', _on_error)
    p.connect('stream-added', _on_source_added)
    p.play()

    g_main_loop.run()
