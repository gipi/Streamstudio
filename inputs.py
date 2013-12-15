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

class VideoSeekableInput(VideoInput, GuiMixin):
    """Manage the GUI of a seekable input"""
    main_class = 'window1'
    def __init__(self):
        super().__init__()
        self._build_gui()


if __name__ == '__main__':
    GObject.threads_init()
    Gst.init(None)
    Gdk.threads_init()

    import sys

    pipeline_string = sys.argv[1] if len(sys.argv) > 1 else 'videotestsrc ! autovideosink'

    # GUI
    b = VideoInput()
    b.show_all()

    def _cb_remove(*args):print 'remove called', args
    def _cb_activated(*args):print 'activated called', args

    b.connect('removed', _cb_remove)
    b.connect('monitor-activated', _cb_activated)

    # PIPELINE
    try:
        pipeline = BasePipeline(pipeline_string)
    except Exception:
        print >>sys.stderr, '''usage: %s \'<pipeline description>\'

Try to pass as pipeline description a thing like

  'filesrc location=/path/to/some-file.mp4 ! decodebin name=demux ! autovideosink demux. ! autoaudiosink'
''' % (sys.argv[0],)
        sys.exit(1)
    def _cb_set_sink(p, imagesink):
        logger.debug('emitted from \'%s\' set-sink signal for \'%s\'' % (
            p, imagesink,
        ))
        b.set_sink(imagesink)
    pipeline.connect('set-sink', _cb_set_sink)
    pipeline.play()

    Gtk.main()
