#!/usr/bin/env python
'''We are trying to 
build a studio for lots of video/audio 
input who generate a virtual webcam as output 

More example in future.'''

import inputs
import sys
from sslog import logger
from gui import GuiMixin

from gi.repository import Gtk, GObject, Gdk
import pipeline

print 'Gtk %d.%d.%d' % (
    Gtk.get_major_version(),
    Gtk.get_minor_version(),
    Gtk.get_micro_version(),
)

class StreamStudio(GuiMixin):
    main_class = 'ssWindow'
    def __init__(self, videodevicepaths, title='StreamStudio'):
        self._build_gui()
        self.main_monitor_widget = self._get_ui_element_by_name('frame1')
        self.main_monitor_widget.set_size_request(600, 400)
        self.sources_vbox = self._get_ui_element_by_name('box3')

        self.videodevicepaths = videodevicepaths
        # this dictionary will have as keys the VideoInput instances
        # and as values the respective video devices.
        self.monitors = {} 

        self.videowidget = inputs.VideoInput()
        childWidget = self.videowidget.main_vbox
        # this is the main monitor so attach it to the left
        childWidget.reparent(self.main_monitor_widget)
        childWidget.show_all()


    def _add_viewer_to_gui(self, devicepath=None):
        """Create a VideoInput attach it to the main GUI and return it.

        Also it possible to associate a dictionary to the instance.
        """
        viewer = inputs.VideoInput() 
        childWidget = viewer.main_vbox
        childWidget.reparent(self.sources_vbox)

        # since we are ready to append, save the position
        # for the "remove" callback
        def _cb_created(obj, *args, **kwargs):
            print '#UAU viewer removed', obj

        def _cb_activated(obj, *args, **kwargs):
            print ' # a monitor has been activated', obj
            try:
                self.pipeline.switch_to(self.monitors[obj])
            except KeyError, e:
                logger.error(list(self.monitors.keys()))
                logger.exception(e)

        viewer.connect('removed', _cb_created)
        viewer.connect('monitor-activated', _cb_activated)

        if devicepath:
            self.monitors[viewer] = devicepath

        childWidget.show_all()

        return viewer

    def _get_monitor_from_devicepath(self, devicepath):
        """Here simply check if the name is main_monitor
        if it is then return the main monitor otherwise create a new VideoInput
        and
        """
        if not devicepath:
            logger.debug("yes")
            return self.videowidget
        else:
            logger.debug("no")
            return self._add_viewer_to_gui(devicepath=devicepath)

    def _cb_for_xsink(self, imagesink, devicepath):
        self.set_sink_for(None, imagesink, devicepath)

    def set_sink_for(self, obj, sink, devicepath):
        """sink is an imagesink instance"""
        logger.debug("set sink %s:%s:%s" % (obj, sink, devicepath,))
        try:
            monitor = self._get_monitor_from_devicepath(devicepath)
            monitor.set_sink(sink)
        except Exception, e:
            logger.exception(e)
        logger.debug("set sink: exit")

    def _on_action_add_new_video_source(self, action):
        self.add_video_source()
    
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

    def _on_show(self, *args):
        # http://blog.yorba.org/jim/2010/10/those-realize-map-widget-signals.html
        # map-event: is a GDK event. This is called when the window is now on-screen,
        #            i.e. the connection is complete. It's like a callback.
        self.pipeline = pipeline.Pipeline([], xsink_cb=self._cb_for_xsink)
        for device in self.videodevicepaths:
            self.pipeline.add_source(device)

        self.pipeline.play()

    def _on_video_source_device_selection(self, filename):
        """
        When the selection is successfully then get the filename
        create the proper pipeline and pass it to self._control_pipeline. 
        """
        self.pipeline.add_source(filename)

    def _alert_message(self, message):
        self.statusbar.push(self._menu_cix,message)
        print message

    def add_video_source(self, data):
        """Open a dialog to choose the proper video device
           then pass chosed file to self._on_device_selection
        """
        fs = Gtk.FileChooserDialog("Choose a video device",None,
                        Gtk.FILE_CHOOSER_ACTION_OPEN,
                        (Gtk.STOCK_CANCEL, Gtk.RESPONSE_CANCEL,
                                        Gtk.STOCK_OPEN, Gtk.RESPONSE_OK))
        fs.set_default_response(Gtk.RESPONSE_OK)
        filter = Gtk.FileFilter()
        filter.set_name("Video devices")
        filter.add_pattern("video*")
        fs.add_filter(filter)
        filter = Gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        fs.add_filter(filter)
        fs.set_current_folder("/dev")
        fs.add_shortcut_folder("/dev")
        response = fs.run()
        if response == Gtk.RESPONSE_OK:
               self._on_video_source_device_selection(fs.get_filename())
        elif response == Gtk.RESPONSE_CANCEL:
              self._alert_message('No video device selected')
        fs.destroy()

    def new_gs_pipeline(self):
        """Opens a dialog window to insert your own gstreamer pipeline"""
        label = Gtk.Label("Insert your already tested gstreamer pipeline:")
        dialog = Gtk.Dialog("Add a Gstreamer pipeline",
                       None,
                       Gtk.DIALOG_MODAL | Gtk.DIALOG_DESTROY_WITH_PARENT,
                       (Gtk.STOCK_CANCEL, Gtk.RESPONSE_REJECT,
                        Gtk.STOCK_OK, Gtk.RESPONSE_ACCEPT))
        dialog.vbox.pack_start(label)
        label.show()
        entry = Gtk.Entry()
        dialog.vbox.pack_start(entry)
        entry.show()
        response = dialog.run()
        if response == -3:
           gspipeline=entry.get_text()
           if gspipeline:
                self._control_pipeline(gspipeline)
                dialog.destroy()
 
    def open(self):
        fs = Gtk.FileChooserDialog("Choose a file with pipelines",None,
                        Gtk.FILE_CHOOSER_ACTION_OPEN,
                        (Gtk.STOCK_CANCEL, Gtk.RESPONSE_CANCEL,
                                        Gtk.STOCK_OPEN, Gtk.RESPONSE_OK))
        fs.set_default_response(Gtk.RESPONSE_OK)
        filter = Gtk.FileFilter()
        filter.set_name("StreamStudio files")
        filter.add_pattern("*.streamstudio")
        fs.add_filter(filter)
        filter = Gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        fs.add_filter(filter)
        #fs.set_current_folder("$HOME/.streamstudio")
        response = fs.run()
        if response == Gtk.RESPONSE_OK:
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

        elif response == Gtk.RESPONSE_CANCEL:
              self._alert_message('pipelines\' configuration file opening aborted')
        fs.destroy()

    def save(self):
        if not len(self.pipelines):
            dialog = Gtk.MessageDialog(self,
                (Gtk.DIALOG_MODAL |
                    Gtk.DIALOG_DESTROY_WITH_PARENT),
                    Gtk.MESSAGE_INFO, Gtk.BUTTONS_OK,
                                   "Choose at least one webcam or add a gstreamer pipeline before saving!")
            dialog.run()
            dialog.destroy()
            return

        fs = Gtk.FileChooserDialog("Choose a file to save active pipelines",None,
                        Gtk.FILE_CHOOSER_ACTION_SAVE,
                        (Gtk.STOCK_CANCEL, Gtk.RESPONSE_CANCEL,
                                        Gtk.STOCK_SAVE, Gtk.RESPONSE_OK))
        fs.set_default_response(Gtk.RESPONSE_OK)
        filter = Gtk.FileFilter()
        filter.set_name("StreamStudio files")
        filter.add_pattern("*.streamstudio")
        fs.add_filter(filter)
        filter = Gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        fs.add_filter(filter)
        #fs.set_current_folder("$HOME/.streamstudio")
        fs.set_do_overwrite_confirmation(True)
        response = fs.run()
        if response == Gtk.RESPONSE_OK:
            filename=fs.get_filename()
            #BUG PRESENT HERE: if you write an existing filename without extension
            #it overwrites file without asking confirmation
            if not filename.split(".")[-1] == "streamstudio":
                filename += ".streamstudio"

                f=open(filename,'w')
                for pipeline in self.pipelines:
                    f.writelines(pipeline+"\n")
                f.close()
            elif response == Gtk.RESPONSE_CANCEL:
                self._alert_message('pipelines\' saving aborted')
            fs.destroy()

    def about(self):
        dialog = Gtk.MessageDialog(self,
            (Gtk.DIALOG_MODAL |
            Gtk.DIALOG_DESTROY_WITH_PARENT),
            Gtk.MESSAGE_INFO,
            Gtk.BUTTONS_OK,
            "We are trying to build a studio for lots of video/audio input who generate a virtual webcam as output"
        )
        dialog.run()
        dialog.destroy()

    def quit(self):
        self.pipeline.kill()
        Gtk.main_quit()

def usage(progname):
    print """usage: %s [video1 video2 ...]
    """ % progname

if __name__ == '__main__':
    GObject.threads_init()
    a = StreamStudio(sys.argv[1:])
    a.show_all()
    Gtk.main()
