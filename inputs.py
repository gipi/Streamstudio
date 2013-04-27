from sslog import logger
from gi.repository import Gtk, GObject


class VideoInput(Gtk.Window):
    '''This class create a viewers with its own toolbar and its own gtk.Window
    for a gstreamer video pipeline who could be imported in other windows 
    using reparenting:

    import inputs
    (...)
    viewer = inputs.VideoInput() 
    viewer.set_pipeline(pipeline)
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

    def __init__(self):
        self.status="PAUSE"
        self.label=""
        Gtk.Window.__init__(self)
        self.set_title(self.get_label())
        self.connect('delete-event', self._on_delete_event)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_size_request(200, 200)
        self.ui_string = """
        <ui>
            <toolbar name='Toolbar'>
                <toolitem action='Play'/>
                <toolitem action='Pause'/>
                <toolitem action='Rec'/>
                <toolitem action='Active'/>
                <separator/>
                <toolitem action='Remove'/>
            </toolbar>
        </ui>"""
        uimgr = self._create_ui()
        uimgr.connect('connect-proxy',
                      self._on_uimanager__connect_proxy)
        uimgr.connect('disconnect-proxy',
                      self._on_uimanager__disconnect_proxy)
        toolbar = uimgr.get_widget('/Toolbar')
        label = Gtk.Label(self.get_label())
        da = Gtk.DrawingArea()
        vbox=Gtk.VBox()
        vbox.pack_start(label, False, True, 0)
        vbox.add(da)
        vbox.pack_end(toolbar, False, True, 0)
        self.main_vbox=vbox
        self.da=da
        self.add(vbox)

    def _on_uimanager__connect_proxy(self, uimgr, action, widget):
        tooltip = action.get_property('tooltip')
        if not tooltip:
            return

        if isinstance(widget, Gtk.MenuItem):
            cid = widget.connect('select', self._on_menu_item__select,
                                 tooltip)
            cid2 = widget.connect('deselect', self._on_menu_item__deselect)
            widget.set_data('pygtk-app::proxy-signal-ids', (cid, cid2))
        #elif isinstance(widget, gtk.ToolButton):
            #cid = widget.child.connect('enter', self._on_tool_button__enter,
            #                           tooltip)
            #cid2 = widget.child.connect('leave', self._on_tool_button__leave)
            #widget.set_data('pygtk-app::proxy-signal-ids', (cid, cid2))

    def _on_uimanager__disconnect_proxy(self, uimgr, action, widget):
        cids = widget.get_data('pygtk-app::proxy-signal-ids')
        if not cids:
            return

        if isinstance(widget, Gtk.ToolButton):
            widget = widget.child

        for name, cid in cids:
            widget.disconnect(cid)

    #def _on_tool_button__enter(self, toolbutton, tooltip):
    #    #self.statusbar.push(self._menu_cix, tooltip)
    #	raise

    #def _on_tool_button__leave(self, toolbutton):
    #    #self.statusbar.pop(self._menu_cix)
    #    raise

    def _on_delete_event(self,window,event):
        Gtk.main_quit()

    def _create_ui(self):
        ag = Gtk.ActionGroup('AppActions')
        actions = [
            ('Play',     Gtk.STOCK_MEDIA_PLAY, '_Play', '',
             'Playing this video input', self._on_action_play),
            ('Pause',     Gtk.STOCK_MEDIA_PAUSE, '_Pause', '',
             'Pause playing this video input', self._on_action_pause),
            ('Rec',     Gtk.STOCK_MEDIA_RECORD, '_Rec', '',
             'Record this video input', self._on_action_rec),
            ('Remove',     Gtk.STOCK_QUIT, '_Remove', '',
             'Remove this video input', self._on_action_remove),
            ('Active',     Gtk.STOCK_OK, '_Active', '',
             'Remove this video input', self._on_action_active),
            ]
        ag.add_actions(actions)
        ui = Gtk.UIManager()
        ui.insert_action_group(ag, 0)
        ui.add_ui_from_string(self.ui_string)
        self.add_accel_group(ui.get_accel_group())
        return ui

    def set_label(self,label):
        self.label=label

    def get_label(self):
        if not self.label:
            self.set_label("New video input")
        return self.label

    def set_sink(self, sink):
        xid = self.da.get_property('window.xid').get_xid()
        assert xid
        self.imagesink = sink
        Gtk.gdk.display_get_default().sync()
        self.imagesink.set_property("force-aspect-ratio", True)
        self.imagesink.set_xwindow_handle(xid)

    def _on_action_play(self, action):
        self.play()

    def _on_action_pause(self, action):
        self.pause()

    def _on_action_rec(self, action):
        self.rec()

    def _on_action_remove(self, action):
        self.remove()

    def _on_action_active(self, action):
        """This action sends the signal that asks
        to who is listening that this monitor wants
        to be activated.
        """
        self.emit('monitor-activated')

    def play(self):
        raise NotImplementedError

    def pause(self):
        raise NotImplementedError

    def rec(self):
        raise NotImplementedError

    def remove(self):
        # TODO: remove itself or emit only the signals?
        self.emit('removed', 100)


if __name__ == '__main__':
    b = VideoInput()
    b.set_label("Test on /dev/video0")
    Gtk.main()
