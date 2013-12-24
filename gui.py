"""Simple class to inizialize its own GUI loading it by a glade file.
"""
from gi.repository import Gtk, Gdk
from sslog import logger
class GuiMixin(object):
    """Mixin to be used to manage easily GUI.

    It uses the parameter 'main_class' to indicate what is the name
    of the root widget that allows to show all.

    The glade file containing the GUI description can be indicated with
    the parameter 'glade_file_path' otherwise it uses the name lowercased of
    the subclass.
    """
    main_class = None
    glade_file_path = None
    main_container_class = None
    drawing_area_class = None

    def _build_gui(self):
        glade_file = '%s.glade' % self.__class__.__name__.lower() if not self.glade_file_path else self.glade_file_path

        print glade_file

        builder = Gtk.Builder()
        builder.add_from_file(glade_file)
        builder.connect_signals(self)

        assert builder != None

        # save it for future access
        self.builder = builder

    def _get_ui_element_by_name(self, name):
        return self.builder.get_object(name)

    def _get_main_class(self):
        return self._get_ui_element_by_name(self.main_class)

    def _get_widget_to_set_sink(self):
        return self._get_ui_element_by_name(self.drawing_area_class)

    def get_main_container(self):
        assert self.main_container_class, "The class '%s' has not defined 'main_container_class' value" % self.__class__
        return self._get_ui_element_by_name(self.main_container_class)

    def show_all(self):
        assert self.main_class, "The class has not defined 'main_class' value."
        self._get_main_class().show_all()

    def reparent_in(self, container):
        self.get_main_container().reparent(container)

        self._get_main_class().destroy()

    def set_sink(self, sink):
        # see <http://gstreamer.freedesktop.org/data/doc/gstreamer/head/gst-plugins-base-libs/html/gst-plugins-base-libs-gstvideooverlay.html>
        Gdk.threads_enter()
        logger.debug('try to set sink with \'%s\'' % (sink,))
        try:
            xid = self._get_widget_to_set_sink().get_property('window').get_xid()
            assert xid
            sink.set_property("force-aspect-ratio", True)
            sink.set_window_handle(xid)
        except Exception, e:
            logger.exception(e)
        finally:
            Gdk.flush()
            Gdk.threads_leave()
