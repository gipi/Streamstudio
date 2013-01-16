"""Simple class to inizialize its own GUI loading it by a glade file.
"""
import gtk

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

    def _build_gui(self):
        glade_file = '%s.glade' % self.__class__.__name__.lower() if not self.glade_file_path else self.glade_file_path

        print glade_file

        builder = gtk.Builder()
        builder.add_from_file(glade_file)
        builder.connect_signals(self)

        # save it for future access
        self.builder = builder

    def _get_ui_element_by_name(self, name):
        return self.builder.get_object(name)

    def show_all(self):
        assert self.main_class, "The class has not defined 'main_class' value."
        self._get_ui_element_by_name(self.main_class).show_all()
