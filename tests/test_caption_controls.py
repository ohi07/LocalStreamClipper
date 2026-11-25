import unittest
from clipper import core

class CaptionControlsTests(unittest.TestCase):
    def test_below_gameplay_and_custom(self):
        below=core.caption_margin(1080,1920,'blur','below',72)
        bottom=core.caption_margin(1080,1920,'blur','bottom',72)
        self.assertGreater(below,bottom)
        self.assertEqual(core.caption_margin(1080,1920,'blur','custom',50),960)
        self.assertEqual(core.caption_margin(1080,1920,'blur','auto',72),below)
    def test_font_settings_rendered(self):
        graph=core.vertical_filtergraph(1080,1920,'blur',True,'pop','DejaVu Sans',50,'below',70)
        self.assertIn('FontName=DejaVu Sans',graph)
        self.assertIn('FontSize=50',graph)
        self.assertIn('Outline=3',graph)
    def test_invalid_font_and_size(self):
        with self.assertRaises(ValueError):core.vertical_filtergraph(1080,1920,'blur',True,'clean','Bad,Font',48)
        with self.assertRaises(ValueError):core.scaled_caption_size(1080,100)
    def test_disabled_captions_unaffected(self):
        self.assertNotIn('subtitles=',core.vertical_filtergraph(1080,1920,'blur',False))
