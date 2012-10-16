#!/usr/bin/env python
'''We are trying to 
build a studio for lots of video/audio 
input who generate a virtual webcam as output 

More example in future.'''

import pygtk
pygtk.require('2.0')
import gtk
import pygst
pygst.require("0.10")
import gst
import inputs


ui_string = """<ui>
  <menubar name='Menubar'>
    <menu action='FileMenu'>
      <menuitem action='Add a webcam'/>
      <menuitem action='Add a gstreamer pipeline'/>
      <menuitem action='Open'/>
      <menuitem action='Save'/>
      <separator/>
      <menuitem action='Quit'/>
    </menu>
    <menu action='HelpMenu'>
      <menuitem action='About'/>
    </menu>
  </menubar>
  <toolbar name='Toolbar'>
    <toolitem action='Add a webcam'/>
    <toolitem action='Add a gstreamer pipeline'/>
    <toolitem action='Open'/>
    <toolitem action='Save'/>
    <separator/>
    <toolitem action='Quit'/>
  </toolbar>
</ui>"""



class StreamStudio(gtk.Window):
    def __init__(self, title='StreamStudio'):
        self.pipelines=[] #active pipelines 
        """
        viewers will be a dictionary with the pipelines as keys
        """
        self.viewers = {} # active viewers (in italiano diremmo spie)
        gtk.Window.__init__(self)
        self.connect('delete-event', self._on_delete_event)
        self.set_position(gtk.WIN_POS_CENTER)
        self.set_size_request(600, 400)
        self.set_title(title)

        main_vbox = gtk.VBox()
        self.main_vbox=main_vbox
        self.add(main_vbox)
        main_vbox.show()

        uimgr = self._create_ui()
        uimgr.connect('connect-proxy',
                      self._on_uimanager__connect_proxy)
        uimgr.connect('disconnect-proxy',
                      self._on_uimanager__disconnect_proxy)

        menubar = uimgr.get_widget('/Menubar')
        main_vbox.pack_start(menubar, expand=False)
        menubar.show()

        toolbar = uimgr.get_widget('/Toolbar')
        main_vbox.pack_start(toolbar, expand=False)
        toolbar.realize()
        toolbar.show()

        viewers_pane=gtk.HPaned()
        sources_vbox = gtk.VBox()
        output_vbox  = gtk.VBox()
        viewers_pane.add1(sources_vbox)
        viewers_pane.add2(output_vbox)
        self.sources_vbox = sources_vbox
        main_vbox.add(viewers_pane)
        viewers_pane.show_all()

        status = gtk.Statusbar()
        main_vbox.pack_end(status, expand=False)
        status.show()
        self.statusbar = status

        self._menu_cix = -1

    def _create_ui(self):
        ag = gtk.ActionGroup('AppActions')
        actions = [
            ('FileMenu', None, '_File'),
            ('Add a webcam',      gtk.STOCK_NEW, '_Add_a_webcam', '<control>N',
             'Add a new webcam', self._on_action_new),
            ('Add a gstreamer pipeline',      gtk.STOCK_DISCONNECT, '_Add_a_gstreamer_pipeline', '<control>G',
             'Add a new, alreasy tested, gstreamer pipeline', self._on_action_new_gs_pipeline),
            ('Open',     gtk.STOCK_OPEN, '_Open', '<control>O',
             'Open a configuration file', self._on_action_open),
            ('Save',     gtk.STOCK_SAVE, '_Save', '<control>S',
             'Save current configuration in a file', self._on_action_save),
            ('Quit',     gtk.STOCK_QUIT, '_Quit', '<control>Q',
             'Quit application', self._on_action_quit),
            ('HelpMenu', None, '_Help'),
            ('About',    None, '_About', None, 'About application',
             self._on_action_about),
            ]
        ag.add_actions(actions)
        ui = gtk.UIManager()
        ui.insert_action_group(ag, 0)
        ui.add_ui_from_string(ui_string)
        self.add_accel_group(ui.get_accel_group())
        return ui

    def _on_uimanager__connect_proxy(self, uimgr, action, widget):
        tooltip = action.get_property('tooltip')
        if not tooltip:
            return

        if isinstance(widget, gtk.MenuItem):
            cid = widget.connect('select', self._on_menu_item__select,
                                 tooltip)
            cid2 = widget.connect('deselect', self._on_menu_item__deselect)
            widget.set_data('pygtk-app::proxy-signal-ids', (cid, cid2))
        elif isinstance(widget, gtk.ToolButton):
            cid = widget.child.connect('enter', self._on_tool_button__enter,
                                       tooltip)
            cid2 = widget.child.connect('leave', self._on_tool_button__leave)
            widget.set_data('pygtk-app::proxy-signal-ids', (cid, cid2))

    def _on_uimanager__disconnect_proxy(self, uimgr, action, widget):
        cids = widget.get_data('pygtk-app::proxy-signal-ids')
        if not cids:
            return

        if isinstance(widget, gtk.ToolButton):
            widget = widget.child

        for name, cid in cids:
            widget.disconnect(cid)

    def _on_menu_item__select(self, menuitem, tooltip):
        self.statusbar.push(self._menu_cix, tooltip)

    def _on_menu_item__deselect(self, menuitem):
        self.statusbar.pop(self._menu_cix)

    def _on_tool_button__enter(self, toolbutton, tooltip):
        self.statusbar.push(self._menu_cix, tooltip)

    def _on_tool_button__leave(self, toolbutton):
        self.statusbar.pop(self._menu_cix)

    def _on_action_new(self, action):
        self.new()
    
    def _on_action_new_gs_pipeline(self, action):
        self.new_gs_pipeline()

    def _on_action_open(self, action):
        self.open()


    def _on_action_save(self, action):
        self.save()

    def _on_action_quit(self, action):
        self.quit()

    def _on_action_about(self, action):
        self.about()

    def _on_delete_event(self, window, event):
        self.quit()

    def _control_pipeline(self, pipeline):
        """Control if pipeline is already present in
           self.pipelines, else add it and create a new VideInput object
        """

        if pipeline not in self.pipelines:
            self.pipelines.append(pipeline)
            self._add_viewer(pipeline)
        else:
            self._alert_message("(%s) pipeline already present" % pipeline)
    
    def _on_device_selection(self, filename):
        """
        When the selection is successfully then get the filename
        create the proper pipeline and pass it to self._control_pipeline. 
        """
        pipeline="v4l2src device=%s ! autovideosink" % filename	
        self._control_pipeline(pipeline)
    
    def _alert_message(self, message):
        self.statusbar.push(self._menu_cix,message)
        print message

    def _add_viewer(self,pipeline):
        viewer = inputs.VideoInput() 
        viewer.set_pipeline(pipeline)
        childWidget = viewer.main_vbox
        childWidget.reparent(self.sources_vbox)
        childWidget.show_all()

        # since we are ready to append, save the position
        # for the "remove" callback
        def _cb_created(obj, data, d=pipeline):
            print '#UAU viewer removed', pipeline
            self.pipelines.remove(pipeline)
            self.viewers.pop(pipeline)

        self.viewers[pipeline] = viewer

        viewer.connect('removed', _cb_created)

    # Override in subclass
    
    def new(self):
        """Open a dialog to choose the proper video device
           then pass chosed file to self._on_device_selection
        """
        
        fs = gtk.FileChooserDialog("Choose a video device",None,
                        gtk.FILE_CHOOSER_ACTION_OPEN,
                        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        fs.set_default_response(gtk.RESPONSE_OK)
        filter = gtk.FileFilter()
        filter.set_name("Video devices")
        filter.add_pattern("video*")
        fs.add_filter(filter)
        filter = gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        fs.add_filter(filter)
        fs.set_current_folder("/dev")
        fs.add_shortcut_folder("/dev")
        response = fs.run()
        if response == gtk.RESPONSE_OK:
               self._on_device_selection(fs.get_filename())
        elif response == gtk.RESPONSE_CANCEL:
              self._alert_message('No video device selected')
        fs.destroy()


    def new_gs_pipeline(self):
        """Opens a dialog window to insert your own gstreamer pipeline"""
        label = gtk.Label("Insert your already tested gstreamer pipeline:")
        dialog = gtk.Dialog("Add a Gstreamer pipeline",
                       None,
                       gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                       (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                        gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        dialog.vbox.pack_start(label)
        label.show()
        entry = gtk.Entry()
        dialog.vbox.pack_start(entry)
        entry.show()
        response = dialog.run()
        if response == -3:
           gspipeline=entry.get_text()
           if gspipeline:
                self._control_pipeline(gspipeline)
                dialog.destroy()
 
    def open(self):
        fs = gtk.FileChooserDialog("Choose a file with pipelines",None,
                        gtk.FILE_CHOOSER_ACTION_OPEN,
                        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        fs.set_default_response(gtk.RESPONSE_OK)
        filter = gtk.FileFilter()
        filter.set_name("StreamStudio files")
        filter.add_pattern("*.streamstudio")
        fs.add_filter(filter)
        filter = gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        fs.add_filter(filter)
        #fs.set_current_folder("$HOME/.streamstudio")
        response = fs.run()
        if response == gtk.RESPONSE_OK:
            filename=fs.get_filename()
            if not filename.split(".")[-1] == "streamstudio":
                filename += ".streamstudio"

            f=open(filename,'r')
            for pipeline in f.readlines():
                pipeline=pipeline[:-1]
                if pipeline not in self.pipelines:
                    self._add_viewer(pipeline)
                else:
                    self._alert_message("(%s) pipeline already active" % pipeline)
            f.close()

        elif response == gtk.RESPONSE_CANCEL:
              self._alert_message('pipelines\' configuration file opening aborted')
        fs.destroy()


    def save(self):
        if not len(self.pipelines):
            dialog = gtk.MessageDialog(self,
                (gtk.DIALOG_MODAL |
                    gtk.DIALOG_DESTROY_WITH_PARENT),
                    gtk.MESSAGE_INFO, gtk.BUTTONS_OK,
                                   "Choose at least one webcam or add a gstreamer pipeline before saving!")
            dialog.run()
            dialog.destroy()
            return

        fs = gtk.FileChooserDialog("Choose a file to save active pipelines",None,
                        gtk.FILE_CHOOSER_ACTION_SAVE,
                        (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        fs.set_default_response(gtk.RESPONSE_OK)
        filter = gtk.FileFilter()
        filter.set_name("StreamStudio files")
        filter.add_pattern("*.streamstudio")
        fs.add_filter(filter)
        filter = gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        fs.add_filter(filter)
        #fs.set_current_folder("$HOME/.streamstudio")
        fs.set_do_overwrite_confirmation(True)
        response = fs.run()
        if response == gtk.RESPONSE_OK:
            filename=fs.get_filename()
            #BUG PRESENT HERE: if you write an existing filename without extension
            #it overwrites file without asking confirmation
            if not filename.split(".")[-1] == "streamstudio":
                filename += ".streamstudio"

                f=open(filename,'w')
                for pipeline in self.pipelines:
                    f.writelines(pipeline+"\n")
                f.close()
            elif response == gtk.RESPONSE_CANCEL:
                self._alert_message('pipelines\' saving aborted')
            fs.destroy()

    def about(self):
        dialog = gtk.MessageDialog(self,
            (gtk.DIALOG_MODAL |
            gtk.DIALOG_DESTROY_WITH_PARENT),
            gtk.MESSAGE_INFO,
            gtk.BUTTONS_OK,
            "We are trying to build a studio for lots of video/audio input who generate a virtual webcam as output"
        )
        dialog.run()
        dialog.destroy()

    def run(self):
        self.show()
        #self._players = []
        gtk.gdk.threads_enter()
        gtk.main()
        gtk.gdk.threads_leave()

    def quit(self):
        gtk.main_quit()

if __name__ == '__main__':
    gtk.gdk.threads_init()
    a = StreamStudio()
    a.run()

