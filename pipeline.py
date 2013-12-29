#!/usr/bin/env python
"""
Main classes to manage gstreamer pipelines construction.
"""
import os
from sslog import logger
from utils import flatten
from gi.repository import Gst, GObject
from conf import Configuration

print 'GObject v%s' % GObject._version
print 'PyGObject v%s' % (
    '.'.join([str(x) for x in GObject.pygobject_version]),
)

import gi
gi.require_version('Gst', '1.0')

import platform; print 'python', platform.python_version()
print Gst.version_string()


conf = Configuration()

class BasePipeline(GObject.GObject):
    """Base class to manage GStreamer pipelines.
    
    This is used to create quick and dirty pipelines, passing as argument
    to the constructor the string with the desired pipeline.

     >>> bp = BasePipeline('videotestsrc pattern=18 ! autovideosink')
     >>> bp.play()

    To avoid unwanted crash remember to initialize all the threading stuffs before.

    The instances expose two signals, 'error' and 'set-sink': the first of course is
    to signal errors happening and the last is emitted when the pipeline is tell us
    that a window will opened to handle some video stream; intercepting it we can
    use an our window.
    """
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

    def _on_message_element(self, message):
        message_name = message.get_structure().get_name()
        src = message.src

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
            elif t == Gst.MessageType.ELEMENT:
                self._on_message_element(message)
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


def _quote_spaces(location):
    return location.replace(' ', '\ ').replace('(', '\(').replace(')', '\)')

class PadPipeline(BasePipeline):
    """Pipeline that decodes streams contained into a file and add automatically
    the needed elements in order to use these.

    The constructor takes one parameter that is the path to the local resource to
    use to build the pipeline.

    For each stream found the signal 'stream-added' is emitted with the stream type
    ('audio' or 'video') and the internal id used to reference it later. Subclasses
    should implement methods _get_video_branch() and _build_audio_branch() if
    the default elements added to the pipeline are not enough for their purposes.

    When no more streams are present the signal 'no-more-streams' is emitted.
    """
    __gsignals__ = {
        'stream-added': (
            GObject.SIGNAL_RUN_LAST,
            GObject.TYPE_NONE,
            (GObject.TYPE_STRING, GObject.TYPE_INT,)
        ),
        'no-more-streams': (
            GObject.SIGNAL_RUN_LAST,
            GObject.TYPE_NONE,
            (),
        ),
        'prepare-video-stream-sink': (
            GObject.SIGNAL_RUN_LAST,
            GObject.TYPE_NONE,
            (GObject.TYPE_OBJECT, GObject.TYPE_INT,)
        ),
    }

    def __init__(self, location):
        self._location = location
        super(PadPipeline, self).__init__(self._build_pipeline_string())

        # 0-indexed audio and video sources
        self._audio_source_counter = 0
        self._audio_elements = []

        self._video_source_counter = 0
        self._video_elements = []

    def _build_pipeline_string(self):
            return 'filesrc location=%s ! decodebin name=demux' % (
                _quote_spaces(self._location),
            )

    def _setup_pipeline(self):
        super(PadPipeline, self)._setup_pipeline()

        # TODO: use '_X' for element intended to not be public
        self.decode = self.player.get_by_name('demux')
        self.video_queue = self.player.get_by_name('video_queue')
        self.audio_queue = self.player.get_by_name('audio_queue')
        self.audiosink = self.player.get_by_name('audiosink')

        self.decode.connect("pad-added", self._on_dynamic_pad)
        self.decode.connect("no-more-pads", self._on_no_more_pads)

        #self.player.set_state(Gst.State.PAUSED)

    def _on_dynamic_pad(self, dbin, pad):
        caps = pad.query_caps(None).to_string()
        logger.debug('dynamic pad with caps %s' % caps)

        if caps.startswith('audio'):
            self._on_audio_dynamic_pad(dbin, pad)
        elif caps.startswith('video'):
            self._on_video_dynamic_pad(dbin, pad)

    def _on_no_more_pads(self, decode):
        self.emit('no-more-streams')

    def _on_message_prepare_window_handle(self, message):
        """Extend the normal method to pass also the stream id upstream"""
        imagesink = message.src
        tpe, stream_id = self._get_stream_id_from_element(imagesink)

        super(PadPipeline, self)._on_message_prepare_window_handle(message)

        self.emit('prepare-video-stream-sink', imagesink, stream_id)

    def _get_video_branch(self):
        """Return a list of element to link in the given order. The last one
        is to link with the pad.
        """
        return [
            Gst.ElementFactory.make('autovideosink', None),
        ]

    def _build_audio_branch(self):
        """Return a list of element to link in the given order. The first one
        is to link with the pad.
        """
        return [
            Gst.ElementFactory.make('tee', None), [
                [Gst.ElementFactory.make('queue', None), Gst.ElementFactory.make('autoaudiosink', None), ],
            ]
        ]

    def _build_branches(self, elements):
        """Create a new branch starting from the given element.

        This method allows to create recursively a new branch: if the list passed
        as argument contains a Tee element, then the following element could be
        a list of lists of elements that will be attached to this Tee element.

        In this case, the elements after the list are ignored.

        NOTE: rememeber to add a queue as first element of each sub-list otherwise the pipeline will hang.
        """
        to_link = None
        is_tee_mode = False
        caps_to_filter_with = None

        # now we loop over each element and link them in the given order
        for el in elements:
            # if we don't have a GstElement probably is a list
            if is_tee_mode and not isinstance(el, Gst.Element):
                for tee_branches in el:
                    to_link.link(self._build_branches(tee_branches))

                break
            elif el.__gtype__.name == 'GstCaps':
                # if we found a caps then avoid the loop and save the caps
                caps_to_filter_with = el
                continue
            else:
                self.player.add(el)

                # http://delog.wordpress.com/2011/07/25/link-dynamic-pads-of-demuxer/
                #  The state of these new elements needs to set to GST_STATE_PLAYING.
                el.set_state(Gst.State.PLAYING)

            if to_link is not None:
                logger.debug(' %s -> %s' % 
                    (to_link.get_name(), el.get_name(),)
                )
                to_link.link_filtered(el, caps_to_filter_with)
                caps_to_filter_with = None

            to_link = el

            is_tee_mode = (el.__gtype__.name == 'GstTee')
            caps_to_filter_with = None

        return elements[0]

    def _on_video_dynamic_pad(self, dbin, pad):
        logger.debug('video pad detected')

        elements = self._get_video_branch()
        sink = self._build_branches(elements)

        # as said, the first element is connected to the source
        pad.link(sink.get_static_pad('sink'))
        logger.debug(' %s <=> %s' %
            (pad, sink.get_name(),)
        )

        self._video_source_counter += 1
        self._video_elements.append(list(flatten(elements)))

        self.emit('stream-added', 'video', self._video_source_counter - 1)

    def _on_audio_dynamic_pad(self, dbin, pad):
        logger.debug('audio pad detected')

        elements = self._build_audio_branch()
        sink = self._build_branches(elements)

        pad.link(sink.get_static_pad('sink'))
        logger.debug(' %s <=> %s' % 
            (pad, sink.get_name(),)
        )

        self._audio_source_counter += 1
        self._audio_elements.append(list(flatten(elements)))

        self.emit('stream-added', 'audio', self._audio_source_counter - 1)

    def _get_stream_id_from_element(self, element):
        """Tell us at what stream the element passed as argument belongs"""
        count = 0
        for stream_elements in self._video_elements:
            count += 1
            if element in stream_elements:
                return ('video', count,)

        count = 0
        for stream_elements in self._audio_elements:
            count += 1
            if element in stream_elements:
                return ('audio', count,)

        print self._audio_elements
        print self._video_elements

        return (None, None,)


class StreamStudioSource(PadPipeline):
    """This class represents a source stream usable by StreamStudio.

    It's a pipeline having a monitor for each one stream made available from the original
    resource associated with a appsink element
    """
    __gsignals__ = {
        'level-change': (# when the audio level change
            GObject.SIGNAL_RUN_LAST,
            GObject.TYPE_NONE,
            (GObject.TYPE_INT, GObject.TYPE_FLOAT,)
        ),
    }
    WIDTH = 320
    HEIGHT = 200
    FRAMERATE = 10

    def __init__(self, *args):
        super(StreamStudioSource, self).__init__(*args)

        self._volumes = {}

        self._video_tee_probe_id = None

    def _on_message_element(self, message):
        super(StreamStudioSource, self)._on_message_element(message)

        if message.get_structure().get_name() == 'level':
            tipe, count = self._get_stream_id_from_element(message.src)
            rms = message.get_structure().get_value('rms')[0]
            peak = message.get_structure().get_value('peak')[0]
            decay = message.get_structure().get_value('decay')[0]

            self.emit('level-change', count - 1, rms)

    def set_volume_for_stream(self, stream_id, value):
        self._volumes[stream_id].set_property('volume', value)

    def _build_audio_branch(self):
        """Return a list of element to link in the given order. The last one
        is to link with the pad.
        """
        volume = Gst.ElementFactory.make('volume', None)
        self._volumes[self._audio_source_counter] = volume
        return [
            Gst.ElementFactory.make('tee', None), [
                [
                    Gst.ElementFactory.make('queue', None),
                    volume,
                    Gst.ElementFactory.make('level', None),
                    Gst.ElementFactory.make('autoaudiosink', None),
                ],
                [Gst.ElementFactory.make('queue', None), Gst.ElementFactory.make('appsink', None),],
            ]
        ]

    def _get_video_branch(self):
        """Return a list of element to link in the given order. The first one
        is the tee to link with the pad that can be used later for other.
        """
        self._video_tee = Gst.ElementFactory.make('tee', None)
        filtr = Gst.Caps.from_string('video/x-raw,width=(int)%d,height=(int)%d,framerate=(fraction)%d/1' % 
            (self.WIDTH, self.HEIGHT, self.FRAMERATE)
        )
        xvimagesink = Gst.ElementFactory.make('xvimagesink', None)
        return [
            self._video_tee, [
                [
                    Gst.ElementFactory.make('queue', None),
                    Gst.ElementFactory.make('videoscale', None),
                    Gst.ElementFactory.make('videorate', None),
                    filtr,
                    xvimagesink,
                ],
            ]
        ]

    def _on_video_dynamic_pad(self, dbin, pad):
        super(StreamStudioSource, self)._on_video_dynamic_pad(dbin, pad)

        # save the src pad in the tee/appsink for attaching/detaching
        self._video_tee_src_pad = self._video_tee.get_request_pad('src_1')

        assert self._video_tee_src_pad

    def _get_appsink_branch_elements(self):
        """"When an appsink is requested this method creates the necessary elements"""
        filtr_sink = Gst.Caps.from_string('video/x-raw,width=(int)%d,height=(int)%d,framerate=(fraction)%d/1,format=(string)RGB16' %
            (conf.get_output_width(), conf.get_output_height(), conf.get_fps())
        )

        queue = Gst.ElementFactory.make('queue', None)
        videoscale = Gst.ElementFactory.make('videoscale', None)
        videorate = Gst.ElementFactory.make('videorate', None)
        videoconvert = Gst.ElementFactory.make('videoconvert', None)

        self._video_app_sink = Gst.ElementFactory.make('appsink', None)
        self._video_app_sink.set_property('max-buffers', 2)
        self._video_app_sink.set_property('drop', True)

        # FIXME: since Caps elements can be removed we create two separate lists
        self._video_app_sink_branch_elements = [
            queue,
            videoscale,
            videorate,
            videoconvert,
            self._video_app_sink,
        ]

        return [
            queue,
            videoscale,
            videorate,
            videoconvert,
            filtr_sink,
            self._video_app_sink,
        ]

    def _remove_elements(self, elements):
        """Utility method that detach elements from the pipeline"""
        # TODO: set the elements to NULL
        logger.debug('remove %s' % elements)

        for el in elements:
            el.set_state(Gst.State.NULL)
            self.player.remove(el)

    def enable_video_src(self):
        """Calling this method we are attacching an appsink to the pipeline so that
        an external application can pull data from it
        """
        elements = self._get_appsink_branch_elements()
        self._video_tee.link(
            self._build_branches(elements)
        )

        self._video_appsink_pad = self._video_app_sink.get_static_pad('sink')
        assert self._video_appsink_pad

        return self._video_app_sink

    def disable_video_src(self):
        """Calling this method detach the branch created with enable_video_src()"""
        if self._video_app_sink is None:
            raise RuntimeWarning('appsink not yet attached')
            return


        def __cb_eos_probe(pad, info, user_data):
            if info.get_event() != Gst.EventType.EOS:
                Gst.PadProbeReturn.OK

            logger.debug('eos on pad %s' % pad)

            self._remove_elements(
                self._video_app_sink_branch_elements
            )

            self._video_app_sink = None
            self._video_appsink_pad = None

            return Gst.PadProbeReturn.DROP

        def __cb_pad_probe(pad, info, user_data):
            logger.debug('pad %s is blocked now' % pad)

            pad.remove_probe(self._video_tee_probe_id)

            self._video_appsink_eos_id = self._video_appsink_pad.add_probe(
                Gst.PadProbeType.EVENT_DOWNSTREAM,
                __cb_eos_probe,
                None
            )

            return Gst.PadProbeReturn.OK

        # add a pad probe and remove elements on the callback
        self._video_tee_probe_id = self._video_tee_src_pad.add_probe(Gst.PadProbeType.BLOCK_DOWNSTREAM, __cb_pad_probe, None)
class V4L2StreamStudioSource(StreamStudioSource):
    def _build_pipeline_string(self):
        return 'v4l2src device=%s ! decodebin name=demux' % self._location

class RemoteStreamStudioSource(StreamStudioSource):
    def _build_pipeline_string(self):
        return 'souphttpsrc location=%s ! decodebin name=demux' % self._location

class ImageStreamStudioSource(StreamStudioSource):
    def _get_video_branch(self):
        """Prepend a 'imagefreeze' element"""
        elements = super(ImageStreamStudioSource, self)._get_video_branch()

        elements.insert(0, Gst.ElementFactory.make('imagefreeze', None))

        return elements

class StreamStudioOutput(BasePipeline):
    """Pipeline used to finally produce the streaming needed."""

    def __init__(self):
        super(StreamStudioOutput, self).__init__(
            'appsrc name=source caps=video/x-raw,format=(string)RGB16,width=(int)%d,height=(int)%d,framerate=(fraction)%d/1 ! videoconvert ! xvimagesink' %
                (conf.get_output_width(), conf.get_output_height(), conf.get_fps())
        )

        self._app_src = self.player.get_by_name('source')

        assert self._app_src

    def enable_external_sources(self):
        """Switch the pipeline to use the appsrc stream"""
        self.switch(True)

    def switch(self, enable):
        logger.debug('switch %s' % enable)
        self._input_selector.set_property('active-pad', self._app_src_pad if enable else self._test_src_pad)

    def disable_exteral_sources(self):
        self.switch(False)

    def get_video_src(self):
        return self._app_src

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
