'''By Pierpa and Packs: This class
add a viewer for a video input in the main 
program window
'''

import pygtk
pygtk.require('2.0')
import gtk
import pygst
pygst.require("0.10")
import gst


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
    '''	
	
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
             'Remove this video input', self._on_action_remove)
            ]
        ag.add_actions(actions)
        ui = gtk.UIManager()
        ui.insert_action_group(ag, 0)
        ui.add_ui_from_string(self.ui_string)
        self.add_accel_group(ui.get_accel_group())
        return ui

    def set_pipeline(self,pipeline):
	self.pipeline=pipeline
	self._pipeline()	

    def get_pipeline(self):
	return self.pipeline

    def set_label(self,label):
	self.label=label	

    def get_label(self):
	if not self.label:
		self.set_label("New video input")
	return self.label

    def _pipeline(self):
	"""
	This method create a pipeline as described in "pipeline"
	and redirect video output into the DrawingArea() passed
	as second argument.

	The callback are created at runtime using python closure.
	"""
	
	def __cb_on_sync():
		def on_sync_message(bus, message):
			if message.structure is None:
				return
			message_name = message.structure.get_name()
			#print '###', message_name

			"""
			following this FAQ 

			http://faq.pygtk.org/index.py?file=faq20.006.htp&req=show
			
			we have to wrap code touching widgets
			with gtk.gdk.threads_enter() and gtk.gdk.threads_leave() otherwise
			errors like 

			python: ../../src/xcb_io.c:221: poll_for_event: asserzione "(((long) (event_sequence) - (long) (dpy->request)) <= 0)" non riuscita.

			will appear.
			"""
			gtk.gdk.threads_enter()
			if message_name == "prepare-xwindow-id":
				# Assign the viewport
				imagesink = message.src
				imagesink.set_property("force-aspect-ratio", True)
				imagesink.set_xwindow_id(self.da.window.xid)

			gtk.gdk.threads_leave()

		return on_sync_message

	def __cb_factory(p):
		def _cb(bus, message):
			t = message.type
			if t == gst.MESSAGE_EOS:
				p.set_state(gst.STATE_NULL)
				self.status="PLAY"
			elif t == gst.MESSAGE_ERROR:
				err, debug = message.parse_error()
				print "Error: %s" % err, debug
				p.set_state(gst.STATE_NULL)
				self.status="PLAY"
		return _cb

	player = gst.parse_launch(self.get_pipeline())
	bus = player.get_bus()
	bus.add_signal_watch()
	bus.enable_sync_message_emission()
	bus.connect("message", __cb_factory(player))
	bus.connect("sync-message::element", __cb_on_sync())
	
	self.player=player

    def _on_action_play(self, action):
        self.play()

    def _on_action_pause(self, action):
        self.pause()

    def _on_action_rec(self, action):
        self.rec()

    def _on_action_remove(self, action):
        self.remove()

    def play(self):
	self.status="PLAY"
	state = gst.STATE_PLAYING
	self.player.set_state(state)

    def pause(self):
	self.status="PAUSE"
	state = gst.STATE_NULL
	self.player.set_state(state)

    def rec(self):
	print "REC function not yet implemented"

    def remove(self):
	self.pause()	
	self.main_vbox.destroy()

    def show(self):
	self.show_all()

    def run(self):	
	self.show()

if __name__ == '__main__':
    
    b = VideoInput()
    b.set_label("Test on /dev/video0")
    b.set_pipeline("v4l2src device=/dev/video0 ! autovideosink")
    b.run()	
    gtk.main()
