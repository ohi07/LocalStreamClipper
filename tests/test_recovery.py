import json, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
from clipper import jobs

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.original=jobs.DATA
        jobs.DATA=Path(self.t.name)
        self.coredata=jobs.core.DATA
        jobs.core.DATA=jobs.DATA
    def tearDown(self):
        jobs.DATA=self.original
        jobs.core.DATA=self.coredata
        self.t.cleanup()
    def test_pause_resume_state_persistent(self):
        j=jobs.create(url='https://youtube.com/watch?v=example',quality='480')
        self.assertEqual(jobs.state(j)['state'],'queued')
        jobs.control(j,'pause');self.assertEqual(jobs.state(j)['state'],'paused')
        # Simulate another process reading the saved JSON.
        self.assertEqual(json.loads((jobs.path(j)/'status.json').read_text())['state'],'paused')
        jobs.control(j,'resume');self.assertEqual(jobs.state(j)['state'],'queued')
    def test_restart_does_not_redownload_finished_job(self):
        j=jobs.create(url='https://twitch.tv/videos/123')
        jobs.update(j,state='running',stage='render')
        with patch.object(jobs.threading,'Thread') as th:
            th.return_value.is_alive.return_value=False
            jobs.startup()
        self.assertEqual(jobs.state(j)['state'],'paused')
        jobs._STOP.set()
    def test_retry_failed_job(self):
        j=jobs.create(url='https://facebook.com/example/videos/123')
        jobs.update(j,state='waiting_network',retry_count=3,next_retry_at=time.time()+90)
        jobs.control(j,'resume')
        s=jobs.state(j)
        self.assertEqual(s['state'],'queued')
        self.assertIsNone(s['next_retry_at'])
        self.assertEqual(s['retry_count'],3)
    def test_invalid_file(self):
        with self.assertRaises(ValueError):jobs.create(local_path='/definitely/not/present.mp4')
    def test_quality_limit(self):
        self.assertIn('height<=720',jobs.detect_quality('720'))
        with self.assertRaises(ValueError):jobs.create(url='https://youtube.com/abc',quality='bad')

if __name__=='__main__':unittest.main()
