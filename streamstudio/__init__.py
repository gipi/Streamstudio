from gi.repository import GObject, Gdk, Gst
from .streamstudio import StreamStudio

def start():
    GObject.threads_init()
    Gst.init(None)
    Gdk.threads_init()

    a = StreamStudio()
    a.run()
