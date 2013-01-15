import unittest
import time

class PipelineTests(unittest.TestCase):
    VIDEO_DEV = "/dev/video0"
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

        try:
            self.p.add_source("/dev/video666")
        except AttributeError:
            pass

        time.sleep(4)
    def test_switch_to_unexistent(self):

        self.p.play()

        try:
            self.p.switch_to("/dev/video666")
        except AttributeError:
            pass

        time.sleep(4)

    def test_switch(self):
        self.p.add_source(PipelineTests.VIDEO_DEV)
        self.p.switch_to(PipelineTests.VIDEO_DEV)

        self.p.play()

        time.sleep(4)

    def test_switch_to_fake(self):
        self.p.add_source(PipelineTests.VIDEO_DEV)
        time.sleep(4)# FIXME: without the sleep it hangs

        self.p.switch_to(PipelineTests.VIDEO_DEV)
        time.sleep(4)
        self.p.switch_to("fake")
        time.sleep(4)

    def test_add_source(self):
        self.p.play()

        self.p.add_source(PipelineTests.VIDEO_DEV)

        time.sleep(4)

    def tearDown(self):
        self.p.kill()
