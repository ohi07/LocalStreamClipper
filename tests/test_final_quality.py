import unittest
from pathlib import Path
from clipper import core, jobs

class FinalQualityTests(unittest.TestCase):
    def test_default_input_1080(self):
        self.assertEqual(jobs.create.__kwdefaults__['quality'], '1080')
    def test_preferred_1080_has_fallback(self):
        fmt=jobs.detect_quality('1080')
        self.assertIn('height<=1080', fmt)
        self.assertIn('bv*+ba/b', fmt)
    def test_best_not_capped(self):
        self.assertEqual(jobs.detect_quality('best'), 'bv*+ba/b')
    def test_blur_graph_is_explicit_yuv420(self):
        g=core.vertical_filtergraph(1080,1920,'blur',True)
        self.assertIn('overlay=',g)
        self.assertIn('format=yuv420p[front]',g)
        self.assertIn('subtitles=captions.srt',g)
    def test_center_graph(self):
        self.assertIn('crop=1080:1920',core.vertical_filtergraph(1080,1920,'center'))
    def test_odd_dimensions_rejected(self):
        with self.assertRaises(ValueError):core.vertical_filtergraph(1079,1920)

if __name__=='__main__': unittest.main()
