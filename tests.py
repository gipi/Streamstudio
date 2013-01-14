import unittest
import time

class PipelineTests(unittest.TestCase):
    def setUp(self):
        import gobject
        gobject.threads_init()
        from pipeline import Pipeline

        self.p = Pipeline([])

    def test_empty_devices_list(self):

        self.p.play()

        time.sleep(4)

    def test_add_unexistent(self):
        self.p.play()

        self.p.add_source("/dev/video666")

        time.sleep(4)
    def test_switch_to_unexistent(self):

        self.p.play()

        self.p.switch_to("/dev/video666")
        time.sleep(4)

    def test_switch(self):
        self.p.add_source("/dev/video1")
        self.p.switch_to("/dev/video1")

        self.p.play()

        time.sleep(4)

    def test_add_source(self):
        self.p.play()

        self.p.add_source("/dev/video1")

        time.sleep(4)

    def tearDown(self):
        self.p.kill()
