from sslog import logger
# GstVideo and GdkX11 are necessary to avoid these bugs
# <https://bugzilla.gnome.org/show_bug.cgi?id=673396>
from gi.repository import Gtk, GObject, Gdk, Gst, GstVideo, GdkX11
from pipeline import BasePipeline, StreamStudioSource, StreamStudioOutput
from gui import GuiMixin



class VideoInput(GObject.GObject, GuiMixin):
    '''This class create a viewers with its own toolbar and its own gtk.Window
    for a gstreamer video pipeline who could be imported in other windows 
    using reparenting:

    import inputs
    (...)
    viewer = inputs.VideoInput() 
    childWidget = viewer.main_vbox
    childWidget.reparent(self.main_vbox)
    childWidget.show_all()

    This is intended to be used as a simple view (think to the MVC paradigm) and made
    available some signals
    '''	
    # http://www.pygtk.org/articles/subclassing-gobject/sub-classing-gobject-in-python.htm#d0e570
    __gsignals__ = {
        'removed': (
            GObject.SIGNAL_RUN_LAST,
            GObject.TYPE_NONE,
            (GObject.TYPE_FLOAT,)
        ),
        'monitor-activated': (
            GObject.SIGNAL_RUN_LAST,
            GObject.TYPE_NONE,
            ()
        )
    }

    main_class = 'vi_window'

    def __init__(self):
        GObject.GObject.__init__(self)
        self._build_gui()

        self.da = self._get_ui_element_by_name('vi_drawingarea')
        self._main_container = self._get_ui_element_by_name('vi_main_container')
        self._main_container.set_size_request(400, 320)
        self.btn_activate = self._get_ui_element_by_name('btn_activate')
        self.btn_remove = self._get_ui_element_by_name('btn_remove')

        self._cb_activated = self._get_ui_element_by_name('cb_active')

        assert self.da
        assert self._main_container
        assert self.btn_activate
        assert self.btn_remove
        assert self._cb_activated

        self._get_main_class().connect('delete-event', self._on_delete_event)

        self.btn_activate.connect('clicked', self._on_action_active)
        self.btn_remove.connect('clicked', self._on_action_remove)

        self._cb_handler_id = self._cb_activated.connect('toggled', self._on_activated)

    def reparent_in(self, container):
        logger.debug('reparenting %s with %s' %
            (self._main_container, container,)
        )
        self._main_container.reparent(container)

    def attach_to_pipeline(self, pipeline):
        if not isinstance(pipeline, BasePipeline):
            raise AttributeError('You have to pass a subclass of BasePipeline, you passed \'%s\'' % pipeline.__class__)

        self.pipeline = pipeline

    def _on_delete_event(self,window,event):
        Gtk.main_quit()

    def set_sink(self, sink):
        Gdk.threads_enter()
        logger.debug('try to set sink with \'%s\'' % (sink,))
        try:
            xid = self.da.get_property('window').get_xid()
            assert xid
            self.imagesink = sink
            #Gdk.display_get_default().sync()
            self.imagesink.set_property("force-aspect-ratio", True)
            self.imagesink.set_window_handle(xid)
        except Exception, e:
            logger.exception(e)
        finally:
            Gdk.threads_leave()

    def _on_action_remove(self, action):
        self.remove()

    def _on_action_active(self, action):
        """This action sends the signal that asks
        to who is listening that this monitor wants
        to be activated.
        """
        self.emit('monitor-activated')

    def remove(self):
        # TODO: remove itself or emit only the signals?
        self.emit('removed', 100)

    def _on_activated(self, checbox):
        """The stream can be activated but not the reverse"""
        # disconnect this callback otherwise when another monitor
        # deselects this we gonna having problem
        checbox.disconnect(self._cb_handler_id)

        checbox.set_sensitive(False)
        self.emit('monitor-activated')


    def deselect(self):
        self._cb_activated.set_sensitive(True)
        self._cb_activated.set_active(False)

        self._cb_handler_id = self._cb_activated.connect('toggled', self._on_activated)

class VideoSeekableInput(VideoInput):
    """Manage the GUI of a seekable input"""
    main_class = 'window1'
    def __init__(self):
        super(VideoSeekableInput, self).__init__()

        # here is the instance of GtkAdjustement and not GtkScale
        self.seeker = self._get_ui_element_by_name('vi_seek')

    def _start_seek_polling(self):
        def query_position():
            position = self.pipeline.get_position()
            duration = self.pipeline.get_duration()

            if duration > 0:
                self.seeker.set_value(position*100/float(duration))

            return True

        logger.debug('attaching position cb')
        self.position_cb_id = GObject.timeout_add(100, query_position)

    def attach_to_pipeline(self, pipeline):
        super(VideoSeekableInput, self).attach_to_pipeline(pipeline)

        def _on_press(*args):
            logger.debug('seek: clicked')
            self.pipeline.player.set_state(Gst.State.PAUSED)

            GObject.source_remove(self.position_cb_id)

        def _on_release(*args):
            new_position = self.seeker.get_value()*self.pipeline.get_duration()/100
            logger.debug('seek: release at %f' % new_position)
            self.pipeline.player.set_state(Gst.State.PLAYING)
            self.pipeline.player.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH,
                new_position)

            self._start_seek_polling()

        # attach the onclick
        self.seeker.connect('button-press-event', _on_press)
        self.seeker.connect('button-release-event', _on_release)

        self._start_seek_polling()

class AudioInput(GObject.GObject, GuiMixin):
    main_class = 'mainWindow'
    glade_file_path = 'volume-meter.glade'

    __gsignals__ = {
        'volume-change': (
            GObject.SIGNAL_RUN_LAST,
            GObject.TYPE_NONE,
            (GObject.TYPE_FLOAT,)
        )
    }

    def __init__(self):
        GObject.GObject.__init__(self)
        self._build_gui()

        self.gui_volume = self.builder.get_object('volumebutton')
        self.gui_level = self.builder.get_object('progressbar')

        assert self.gui_level
        assert self.gui_volume

        self.gui_volume.connect('value-changed', self._on_volume_changed)

    def _on_volume_changed(self, widget, value):
        print value
        self.emit('volume-change', value)

    def _rescale_db_to_level(self, db_value):
        """Since the level is from 0 to 100 but the db levels are(?) in the
        range -100 to 20, we use this function to shift and rescale

        0/-100 : 100/20
        """
        db_min    = -100.0
        db_max    = 20.0
        level_min = 0.0
        level_max = 1.0

        v = level_min + abs(db_value) / (db_max - db_min) * (level_max - level_min)

        return v

    def set_gui_volume(self, volume_level):
        self.gui_volume.set_value(volume_level)


    def set_gui_level(self, value):
        self.gui_level.set_fraction(self._rescale_db_to_level(value))

    def reparent_in(self, container):
        self._get_ui_element_by_name('vi_main_container').reparent(container)


class StreamStudioMonitorInput(GObject.GObject, GuiMixin):
    """Class that take a pipeline and create on need the monitor elements
    needed to show the related stream.

    When the stream has finished, the window emit the signal blabla
    """
    __gsignals__ = {
        'initializated': (
            GObject.SIGNAL_RUN_LAST,
            GObject.TYPE_NONE,
            ()
        ),
    }
    main_class = 'ui_ssmonitorwindow'
    main_container_class = 'box1'
    def __init__(self, pipeline):
        GObject.GObject.__init__(self)

        self.pipeline = pipeline

        self._build_gui()

        # this is the hbox will contain the audio and video
        self._monitor_container = self._get_ui_element_by_name('ui_monitor_container')

        # here is the instance of GtkAdjustement and not GtkScale
        self.seeker = self._get_ui_element_by_name('ss_seek')

        self._connect_signals()

        # dicts with as key the stream-id and as value the GtkWidget
        self._audio_streams = {}
        self._video_streams = {}

        # take memory of audio/video stream selected
        self._video_stream_selected = None
        self._audio_stream_selected = None

    def _connect_signals(self):
        self.pipeline.connect('stream-added', self._on_stream_added)
        self.pipeline.connect('set-sink', self._on_set_sink)
        self.pipeline.connect('no-more-streams', self._on_no_more_streams)
        self.pipeline.connect('level-change', self._on_level_change)

        # attach the onclick
        self.seeker.connect('button-press-event', self._on_press)
        self.seeker.connect('button-release-event', self._on_release)

        self._start_seek_polling()

        self._get_main_class().connect('delete-event', self._on_quit)

    def _on_quit(self, window, event):
        Gtk.main_quit()

    def _on_set_sink(self, pipeline, imagesink):
        _type, stream_id = pipeline._get_stream_id_from_element(imagesink)

        self._video_streams[stream_id - 1].set_sink(imagesink)

    def _on_no_more_streams(self, pipeline):
        self.emit('initializated')

    def _on_level_change(self, pipeline, stream_id, level_value):
        Gdk.threads_enter()
        try:
            self._audio_streams[stream_id].set_gui_level(level_value)
        except Exception as e:
            logger.error(e)
        finally:
            Gdk.threads_leave()

    def _start_seek_polling(self):
        def query_position():
            position = self.pipeline.get_position()
            duration = self.pipeline.get_duration()

            if duration > 0:
                Gdk.threads_enter()
                try:
                    self.seeker.set_value(position*100/float(duration))
                except Exception as e:
                    logger.error(e)
                finally:
                    Gdk.threads_leave()

            return True

        logger.debug('attaching position cb')
        self.position_cb_id = GObject.timeout_add(100, query_position)

    def _on_press(self, *args):
        logger.debug('seek: clicked')
        self.pipeline.player.set_state(Gst.State.PAUSED)

        GObject.source_remove(self.position_cb_id)

    def _on_release(self, *args):
        new_position = self.seeker.get_value()*self.pipeline.get_duration()/100
        logger.debug('seek: release at %f' % new_position)
        self.pipeline.player.set_state(Gst.State.PLAYING)
        self.pipeline.player.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH,
            new_position)

        self._start_seek_polling()

    def _on_stream_added(self, pipeline, stream_type, count):
        """Use this to configure the GUI for each stream."""
        logger.debug('_on_stream_added %s-%d' % (stream_type, count,))
        if stream_type == 'audio':
            Gdk.threads_enter()
            vi = AudioInput()
            vi.show_all()

            vi.reparent_in(self._monitor_container)
            vi._get_main_class().destroy()
            Gdk.threads_leave()

            self._audio_streams[count] = vi
            def _cb_on_volume_change(vinput, value):
                self.pipeline.set_volume_for_stream(count, value)

            vi.connect('volume-change', _cb_on_volume_change)
        elif stream_type == 'video':
            Gdk.threads_enter()

            videoinput = VideoInput()
            videoinput.reparent_in(self._monitor_container)

            videoinput.show_all()
            # this is MUST stay here otherwise the old window is not destroyed
            videoinput._get_main_class().destroy()

            def __cb_on_monitor_activated(vi):
                self._video_stream_selected = vi
                self.emit('video-stream-selected', count)

            videoinput.connect('monitor-activated', __cb_on_monitor_activated)

            Gdk.threads_leave()

            self._video_streams[count] = videoinput

    def deselect_video(self):
        self._video_stream_selected.deselect()

    def deselect_audio(self):
        self._audio_stream_selected.deselect()


class StreamStudioMonitorOutput(GObject.GObject, GuiMixin):
    __gsignals__ = {
        'initializated': (
            GObject.SIGNAL_RUN_LAST,
            GObject.TYPE_NONE,
            ()
        ),
    }
    main_class = 'window'
    main_container_class = 'box1'
    def __init__(self, pipeline):
        GObject.GObject.__init__(self)
        if not isinstance(pipeline, StreamStudioOutput):
            raise TypeError('we need StreamStudioOutput instance not %s' % pipeline)

        self._build_gui()

        self.da = self._get_ui_element_by_name('drawingarea')
        self._switch_test = self._get_ui_element_by_name('switch_test')

        self.pipeline = pipeline

        self._connect_signal()

    def _connect_signal(self):
        self.pipeline.connect('set-sink', self._on_set_sink)
        self._switch_test.connect('notify::active', self._on_toggle_test)
        self._get_main_class().connect('delete-event', self._on_quit)

    def _on_toggle_test(self, sw, *args):
        self.pipeline.switch(self._switch_test.get_state() == Gtk.StateType.ACTIVE)

    def _on_set_sink(self, pipeline, imagesink):
        Gdk.threads_enter()
        try:
            xid = self.da.get_property('window').get_xid()
            assert xid
            Gdk.flush()
            imagesink.set_property("force-aspect-ratio", True)
            imagesink.set_window_handle(xid)

            self.emit('initializated')
        except Exception, e:
            logger.exception(e)
        finally:
            Gdk.threads_leave()

    def _on_quit(self, window, event):
        Gtk.main_quit()



if __name__ == '__main__':
    GObject.threads_init()
    Gst.init(None)
    Gdk.threads_init()

    import sys

    # PIPELINE
    try:    
        pipeline = StreamStudioSource(sys.argv[1])
    except Exception as e:
        print >>sys.stderr, 'usage: %s <filepath>' % (sys.argv[0],)
        logger.error(e)
        sys.exit(1)

    # GUI
    b = StreamStudioMonitorInput(pipeline)
    b.show_all()

    pipeline.play()


    Gtk.main()
