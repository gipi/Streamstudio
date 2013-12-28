from gi.repository import GObject


class Configuration(GObject.GObject):
    def __init__(self):
        GObject.GObject.__init__(self)

    def get_output_width(self):
        return 640

    def get_output_height(self):
        return 480

    def get_fps(self):
        return 10
