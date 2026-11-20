import unittest
from clipper.core import validate_url, srt_timestamp, make_windows, select_highlights

class CoreTests(unittest.TestCase):
    def test_url_allowlist(self):
        self.assertEqual(validate_url("https://www.youtube.com/watch?v=abc"), "https://www.youtube.com/watch?v=abc")
        self.assertTrue(validate_url("https://clips.twitch.tv/SomeClip"))
        with self.assertRaises(ValueError): validate_url("http://127.0.0.1/private")
        with self.assertRaises(ValueError): validate_url("https://youtube.com.evil.test/video")
    def test_srt_time(self):
        self.assertEqual(srt_timestamp(3661.124), "01:01:01,124")
    def test_candidates(self):
        data = [{"start": 3, "end": 10, "text": "wow this is unbelievable!", "words": []},
                {"start": 25, "end": 32, "text": "today we learned a very interesting thing", "words": []}]
        candidates = make_windows(data, 20, 60)
        self.assertTrue(candidates)
        self.assertTrue(select_highlights(candidates, 2))

if __name__ == "__main__": unittest.main()
