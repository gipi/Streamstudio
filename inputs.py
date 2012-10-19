import gobject
import pygtk
pygtk.require('2.0')
import gtk
import pygst
pygst.require("0.10")
import gst
from sslog import logger


class VideoInput(gtk.Window):
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
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            (gobject.TYPE_FLOAT,)
        ),
        'monitor-activated': (
            gobject.SIGNAL_RUN_LAST,
            gobject.TYPE_NONE,
            ()
        )
    }

    def __init__(self):
        self.status="PAUSE"
        self.label=""
        gtk.Window.__init__(self)
        self.set_title(self.get_label())
        self.connect('delete-event', self._on_delete_event)
        self.set_position(gtk.WIN_POS_CENTER)
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
        label = gtk.Label(self.get_label())
        da = gtk.DrawingArea()
        vbox=gtk.VBox()
        vbox.pack_start(label,expand=False)
        vbox.add(da)
        vbox.pack_end(toolbar,expand=False)
        self.main_vbox=vbox
        self.da=da
        self.add(vbox)

    def _on_uimanager__connect_proxy(self, uimgr, action, widget):
        tooltip = action.get_property('tooltip')
        if not tooltip:
            return

        if isinstance(widget, gtk.MenuItem):
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

        if isinstance(widget, gtk.ToolButton):
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
        gtk.main_quit()

    def _create_ui(self):
        ag = gtk.ActionGroup('AppActions')
        actions = [
            ('Play',     gtk.STOCK_MEDIA_PLAY, '_Play', '',
             'Playing this video input', self._on_action_play),
            ('Pause',     gtk.STOCK_MEDIA_PAUSE, '_Pause', '',
             'Pause playing this video input', self._on_action_pause),
            ('Rec',     gtk.STOCK_MEDIA_RECORD, '_Rec', '',
             'Record this video input', self._on_action_rec),
            ('Remove',     gtk.STOCK_QUIT, '_Remove', '',
             'Remove this video input', self._on_action_remove),
            ('Active',     gtk.STOCK_OK, '_Active', '',
             'Remove this video input', self._on_action_active),
            ]
        ag.add_actions(actions)
        ui = gtk.UIManager()
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
        xid = self.da.window.xid
        assert xid
        self.imagesink = sink
        # without this the switch works pretty bad
        #  http://developer.gnome.org/pygtk/stable/class-gdkdisplay.html#method-gdkdisplay--sync
        gtk.gdk.threads_enter()
        gtk.gdk.display_get_default().sync()
        self.imagesink.set_property("force-aspect-ratio", True)
        self.imagesink.set_xwindow_id(xid)
        gtk.gdk.threads_leave()

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
    gtk.main()
