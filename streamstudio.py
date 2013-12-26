#!/usr/bin/env python
'''We are trying to 
build a studio for lots of video/audio 
input who generate a virtual webcam as output 

More example in future.'''

import inputs
import sys
from sslog import logger
from gui import GuiMixin

from gi.repository import Gtk, GObject, Gdk, Gst
import pipeline

print 'Gtk %d.%d.%d' % (
    Gtk.get_major_version(),
    Gtk.get_minor_version(),
    Gtk.get_micro_version(),
)

class StreamStudio(GuiMixin):
    main_class = 'ssWindow'
    def __init__(self):
        self._build_gui()
        self._main_monitor_container = self._get_ui_element_by_name('frame1')
        self.sources_vbox = self._get_ui_element_by_name('box3')

        self._pipeline_sources = []
        self._gui_inputs = []

        self._gui_video_selected = None
        self._gui_audio_selected = None

        def __cb_on_show_event(w):
            self._configure_initial_pipeline()
            self._start_initial_pipeline()

        self._get_main_class().connect('show', __cb_on_show_event)

    def _configure_initial_pipeline(self):
        """Create the output pipeline"""
        self._output_pipeline = pipeline.StreamStudioOutput()
        self._output_widget = inputs.StreamStudioMonitorOutput(self._output_pipeline)

        def __cb_on_show(ssmo):
            try:
                self._output_widget.reparent_in(self._main_monitor_container)
            except Exception as e:
                logger.error(e)
            finally:
                pass

        self._output_widget._get_main_class().connect('show', __cb_on_show)

        self._output_widget.show_all()

    def _start_initial_pipeline(self):
        self._output_pipeline.play()

    def _add_source_pipeline(self, filename):
        p = pipeline.StreamStudioSource(filename)
        w = inputs.StreamStudioMonitorInput(p)

        def __cb_on_show(ssmo):
            # here we don't need Gdk.threads_enter()/leave()
            # since it's called from the right thread
            w.reparent_in(self.sources_vbox)
        def __cb_on_video_stream_activated(monitorinput, stream_id):
            logger.info('selected stream %d from %s' %
                (stream_id, p,)
            )
            if self._gui_video_selected is not None:
                self._gui_video_selected.deselect_video()

            self._gui_video_selected = monitorinput

        w._get_main_class().connect('show', __cb_on_show)
        w.connect('video-stream-selected', __cb_on_video_stream_activated)

        w.show_all()

        self._gui_inputs.append(w)

        p.play()
        w.show_all()

        def __cb_on_activated(ssmo):
            Gdk.threads_enter()
            w.reparent_in(self.sources_vbox)
            Gdk.threads_leave()

        w.connect('initializated', __cb_on_activated)

        p.play()

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

    def _on_video_source_device_selection(self, filename):
        """
        When the selection is successfully then get the filename
        create the proper pipeline and pass it to self._control_pipeline. 
        """

    def _alert_message(self, message):
        self.statusbar.push(self._menu_cix,message)
        print message

    def _open_dialog(self, title, patterns, current_folder_path, callback):
        fs = Gtk.FileChooserDialog(title, None,
                        Gtk.FileChooserAction.OPEN,
                        (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

        fs.set_default_response(Gtk.ResponseType.OK)

        for name, pattern in patterns:
            filter = Gtk.FileFilter()
            filter.set_name(name)
            filter.add_pattern(pattern)
            fs.add_filter(filter)

        try:
            fs.set_current_folder(current_folder_path)
            fs.add_shortcut_folder(current_folder_path)
        except:
            pass# shortcut already exists
        response = fs.run()

        if response == Gtk.ResponseType.OK:
               callback(fs.get_filename())
        elif response == Gtk.ResponseType.CANCEL:
              self._alert_message('No video device selected')
        fs.destroy()

    def add_video_source(self, data):
        """Open a dialog to choose the proper video device
           then pass chosed file to self._on_device_selection
        """
        self._open_dialog(
            'Choose you device to open',
            [
                ('video devices', 'video*'),
                ('All files', '*'),
            ],
            '/dev',
            self._on_video_source_device_selection)

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
        import os
        self._open_dialog(
            'Choose a file to open',
            [
                ('All files', '*'),
            ],
            os.path.expanduser('~'),
            self._on_video_source_device_selection)

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
        self._output_pipeline.kill()
        Gtk.main_quit()

    def run(self):
        self.show_all()

        Gtk.main()

def usage(progname):
    print """usage: %s [video1 video2 ...]
    """ % progname

if __name__ == '__main__':
    GObject.threads_init()
    Gst.init(None)
    Gdk.threads_init()

    a = StreamStudio()
    a.run()
