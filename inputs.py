from sslog import logger
# GstVideo and GdkX11 are necessary to avoid these bugs
# <https://bugzilla.gnome.org/show_bug.cgi?id=673396>
from gi.repository import Gtk, GObject, Gdk, Gst, GstVideo, GdkX11
from pipeline import BasePipeline
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
        self.btn_activate = self._get_ui_element_by_name('btn_activate')
        self.btn_remove = self._get_ui_element_by_name('btn_remove')

        self._get_main_class().connect('delete-event', self._on_delete_event)

        self.btn_activate.connect('clicked', self._on_action_active)
        self.btn_remove.connect('clicked', self._on_action_remove)

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

if __name__ == '__main__':
    GObject.threads_init()
    Gst.init(None)
    Gdk.threads_init()

    import sys

    pipeline_string = 'filesrc location=%s name=src ! decodebin name=demux ! autovideosink demux. ! autoaudiosink' % sys.argv[1] if len(sys.argv) > 1 else 'videotestsrc ! autovideosink'

    # GUI
    b = VideoSeekableInput()
    b.show_all()

    def _cb_remove(*args):print 'remove called', args
    def _cb_activated(*args):print 'activated called', args

    b.connect('removed', _cb_remove)
    b.connect('monitor-activated', _cb_activated)

    # PIPELINE
    try:
        pipeline = BasePipeline(pipeline_string)
    except Exception:
        print >>sys.stderr, 'usage: %s <filepath>' % (sys.argv[0],)
        sys.exit(1)
    def _cb_set_sink(p, imagesink):
        logger.debug('emitted from \'%s\' set-sink signal for \'%s\'' % (
            p, imagesink,
        ))
        b.set_sink(imagesink)
    pipeline.connect('set-sink', _cb_set_sink)
    pipeline.play()

    b.attach_to_pipeline(pipeline)

    Gtk.main()
