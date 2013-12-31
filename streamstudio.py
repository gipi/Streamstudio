#!/usr/bin/env python
'''We are trying to 
build a studio for lots of video/audio 
input who generate a virtual webcam as output 

More example in future.
Appsink will internally use a queue to collect buffers from the streaming thread.
If the application is not pulling samples fast enough, this queue will consume a
lot of memory over time. The "max-buffers" property can be used to limit the queue
size. The "drop" property controls whether the streaming thread blocks or if older
buffers are dropped when the maximum queue size is reached. Note that blocking the
streaming thread can negatively affect real-time performance and should be avoided.
'''

import inputs
import sys
from sslog import logger
from gui import GuiMixin

from gi.repository import Gtk, GObject, Gdk, Gst
import pipeline
# lock use inspired from this <https://github.com/kivy/kivy/blob/31ba89c6c7661dcc6fa6916b46be8a0381874e5c/kivy/core/video/video_gstreamer.py>
from threading import Lock
from conf import Configuration

print 'Gtk %d.%d.%d' % (
    Gtk.get_major_version(),
    Gtk.get_minor_version(),
    Gtk.get_micro_version(),
)

conf = Configuration()

class SourceController(GObject.GObject):
    """Link together the trasmitting appsink with the output's appsrc.

    To initialize it you must pass an instance of StreamStudioOutput pipeline
    as argument in its constructor.

     >>> op = StreamStudioOutput()
     >>> sc = SourceController(sc)

    This controller allows two states of trasmission: a state called 'carosello'
    that is a test state, showing an alternating white/black screen and the real
    trasmitting state where the output came from the appsink.

    To switch between these two states you can use the switch_to_carosello() method

     >>> sc.switch_to_carosello(True)

    In order to enable/change the trasmitting StreamStudioSource you have to use
    the swap_source() method, passing the pipeline's appsink you want to transmit.

     >>> ip = StreamStudioSource('whatever.mp4')
     >>> ip.play()
     >>> sc.swap_source(ip.enable_video_src())
    """
    def __init__(self, output_pipeline):
        GObject.GObject.__init__(self)

        self._output = output_pipeline
        self._actual_input = None
        self._actual_pipeline = None

        self._src_handler_id = None

        self._check_data_id = None
        self.timestamp = 0

        self._is_carosello = True
        self.isWhite = True

        self._data = None
        self._lock = Lock()

        self._output.get_video_src().connect('need-data', self._on_need_data)
        self._output.get_video_src().connect('enough-data', self._on_enough_data)

        GObject.timeout_add_seconds(1, self._switch_color)

    def _switch_color(self):
        self.isWhite = not self.isWhite

        return True

    def _dump(self, width, height, depth, isWhite):
        """Return a black/white buffer"""
        # http://gstreamer.freedesktop.org/data/doc/gstreamer/head/manual/html/section-data-spoof.html#section-spoof-appsrc
        size = width * height * depth
        bffer = Gst.Buffer.new_allocate(None, size, None)

        bffer.memset(0, 0x00 if isWhite else 0xff, size)

        bffer.pts = self.timestamp
        bffer.duration = Gst.util_uint64_scale_int(1, Gst.SECOND, 30)

        # NOTE: if you remove this line below the stream after the first
        # switch doesn't re-switch and the stream appears lagging
        self.timestamp += bffer.duration

        return bffer

    def _on_need_data(self, appsrc, *args):
        #logger.debug('need data')
        if not self._check_data_id:
            self._check_data_id = GObject.idle_add(self._push_data, appsrc)

    def _on_enough_data(self, appsrc):
        self._remove_push_data_cb()

    def _on_new_sample(self, appsink):
        with self._lock:
            bffer = appsink.emit('pull-sample')
            self._data = bffer


    def _remove_push_data_cb(self):
        if self._check_data_id:
            GObject.source_remove(self._check_data_id)
            self._check_data_id = None

    def _copy_from_data(self):
        with self._lock:
            if not self._data:
                return None

            bffer = self._data.get_buffer().copy()

            self._data = None

        try:
            bffer.pts = self.timestamp
        except ValueError as e:
            logger.error('%d' % self.timestamp)
            Gtk.main_quit()

        self.timestamp += bffer.duration

        return bffer

    def _push_data(self, source):
        bff = self._copy_from_data() if not self._is_carosello else self._dump(conf.get_output_width(), conf.get_output_height(), 2, self.isWhite)

        if bff is None:
            return True

        result  = source.emit('push-buffer', bff)

        if result != Gst.FlowReturn.OK:
            logger.debug('error on on_need_data: %s' % result)
            Gtk.main_quit()

        return True

    def _stop_actual_video_source(self):
        if self._src_handler_id is not None:
            self._actual_input.disconnect(self._src_handler_id)
            self._actual_input.set_property('emit-signals', False)

            self._src_handler_id = None

    def _remove_actual_video_source(self):
        self._actual_input = None

    def _set_actual_video_input(self, appsink):
        self._actual_input = appsink
    def _start_actual_video_input(self):
        self._src_handler_id = self._actual_input.connect('new-sample', self._on_new_sample)
        self._actual_input.set_property('emit-signals', True)
    def swap_source(self, pipeline):
        """Change the trasmitting appsink"""
        logger.debug('swap source to pipeline %s' % pipeline)

        """Steps:
         1. block new pipeline
         2. attach appsink
         3. block old pipeline
         4. detach appsink old pipeline
         5. unblock new pipeline
         6. unblock old pipeline
        """
        self._tmp_id = None
        self._tmp_id_bis = None

        self._tmp_id_tris = None

        def __cb_on_block_old(old_pipe):
            logger.debug('onn block old')
            old_pipe.disconnect(self._tmp_id_tris)
            old_pipe.disable_video_src()

            self._start_actual_video_input()

            self._actual_pipeline.unblock()

            #old_pipe.unblock()

        def __cb_on_sink_ready(pipe, appsink):
            logger.debug('sink-ready received with %s' % appsink)
            pipe.disconnect(self._tmp_id_bis)

            _tmp_old_pipe = self._actual_pipeline

            # if there is a old input going, block it and do stuffs when is really blocked
            #if _tmp_old_pipe is not None:
            #    self._tmp_id_tris = _tmp_old_pipe.connect('block', __cb_on_block_old)

            self._stop_actual_video_source()
            # here the new input
            self._actual_pipeline = pipe
            self._set_actual_video_input(appsink)

            #if not self.is_carosello():
            self._start_actual_video_input()

            if _tmp_old_pipe is not None:
                _tmp_old_pipe.disable_video_src()

            self._actual_pipeline.unblock()

        def __cb_on_block(pipe):
            logger.debug('on block from %s' % pipe)
            pipeline.disconnect(self._tmp_id)

            self._tmp_id_bis = pipe.connect('sink-ready', __cb_on_sink_ready)

            pipe.enable_video_src()

        self._tmp_id = pipeline.connect('block', __cb_on_block)

        pipeline.block()

    def switch_to_carosello(self, enable):
        """Change from carosello to trasmitting state"""
        self._is_carosello = enable

    def is_carosello(self):
        return self._is_carosello

class StreamStudio(GuiMixin):
    main_class = 'ssWindow'
    def __init__(self):
        self._build_gui()
        self._main_monitor_container = self._get_ui_element_by_name('frame1')
        self.sources_vbox = self._get_ui_element_by_name('box3')

        self._pipeline_sources = []
        self._gui_inputs = []

        self._pipeline_video_selected = None
        self._gui_video_selected = None
        self._gui_audio_selected = None

        def __cb_on_show_event(w):
            self._configure_initial_pipeline()
            self._start_initial_pipeline()

            self._switch_controller = SourceController(self._output_pipeline)

            def __cb_on_switch(monitor_output, enable):
                self._switch_controller.switch_to_carosello(enable)

            # connect the carosello/real stream switch with the controller
            self._output_widget.connect('switch', __cb_on_switch)

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
            self._pipeline_video_selected = p

            # enable the video src that when ready will emit
            # the 'sink-ready' signal
            self._switch_controller.swap_source(p)

        w._get_main_class().connect('show', __cb_on_show)
        w.connect('video-stream-selected', __cb_on_video_stream_activated)

        w.show_all()

        self._gui_inputs.append(w)

        p.play()

    def _add_device_source_pipeline(self, filename):
        p = pipeline.V4L2StreamStudioSource(filename)
        w = inputs.StreamStudioMonitorInput(p)

        def __cb_on_activated(ssmo):
            Gdk.threads_enter()
            w.reparent_in(self.sources_vbox)
            Gdk.threads_leave()

        def __cb_on_video_stream_activated(monitorinput, stream_id):
            logger.info('selected stream %d from %s' %
                (stream_id, p,)
            )
            if self._gui_video_selected is not None:
                self._gui_video_selected.deselect_video()

            self._gui_video_selected = monitorinput

            self._switch_controller.swap_source(p.get_video_src())

        w.connect('initializated', __cb_on_activated)
        w.connect('video-stream-selected', __cb_on_video_stream_activated)

        w.show_all()

        self._gui_inputs.append(w)

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

    def _on_video_source_file_selection(self, filename):
        self._add_source_pipeline(filename)

    def _on_video_source_device_selection(self, filename):
        """
        When the selection is successfully then get the filename
        create the proper pipeline and pass it to self._control_pipeline. 
        """
        self._add_device_source_pipeline(filename)

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
            self._on_video_source_file_selection)

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
