from pathlib import Path
import pytest
from clipper import jobs, core

def test_window_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, 'DATA', tmp_path)
    monkeypatch.setattr(core, 'DATA', tmp_path)
    jid=jobs.create(url='https://www.youtube.com/watch?v=abc123',range_start=8*3600,range_end=8*3600+1800,captions=False)
    state=jobs.state(jid)
    assert state['range_start']==28800 and state['range_end']==30600
    assert state['captions'] is False
    with pytest.raises(ValueError):
        jobs.create(url='https://www.youtube.com/watch?v=abc123',range_start=10,range_end=5)
    with pytest.raises(ValueError):
        jobs.create(url='https://www.youtube.com/watch?v=abc123',range_start=10,range_end=100,backend='mdm')

def test_suggested_title_and_style():
    assert 'Stream Name' in jobs.suggest_title('Stream Name Livestream','Hello there',1)
    assert len(jobs.suggest_title('A'*500,'',20)) <= 100
    assert 'subtitles=captions.srt' not in core.vertical_filtergraph(1080,1920,'blur',False)
    assert 'subtitles=captions.srt' in core.vertical_filtergraph(1080,1920,'blur',True,'pop')
