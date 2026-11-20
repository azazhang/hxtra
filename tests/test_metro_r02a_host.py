"""Host parser contract for METRO-TAPSYNC-R02A-M4EDGE firmware."""
import struct
import pytest
import metro_tapsync_r02a_probe as r02


def test_replies_are_little_endian_u32_counters_with_exact_revision():
    raw=struct.pack('<3I', 1234,5,r02.SENTINEL)
    assert r02.decode(raw)['tap_led_on_count']==1234
    assert r02.decode(raw)['metro_41c_enable_count']==5
    assert r02.decode(raw)['revision']=='METRO-TAPSYNC-R02A-M4EDGE'


def test_unsupported_or_older_firmware_is_rejected():
    for raw in (b'',b'\xc4\x0c',struct.pack('<3I',1,2,0)):
        with pytest.raises(ValueError):r02.decode(raw)
