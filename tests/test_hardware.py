from clipper import hardware

def test_host_info():
    h=hardware.host_info()
    assert h['os']
    assert h['threads']>=1
    assert isinstance(h['apple_silicon'],bool)

def test_invalid_encoder():
    try:hardware.encoder_choice('imaginary')
    except ValueError:pass
    else:assert False

def test_encoder_flags():
    for name in ['cpu','nvenc','amf','qsv','videotoolbox']:
        flags=hardware.encode_args(name,'veryfast')
        assert flags[:1] == ['-c:v']

def test_auto_has_fallback():
    if hardware.encoder_works('cpu'):
        assert hardware.encoder_choice('cpu')=='cpu'
