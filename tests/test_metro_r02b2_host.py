"""METRO-TAPSYNC-R02B2-AUDIO-PHASE host parser contract."""
import struct
import pytest
import metro_tapsync_r02b2_probe as p


def raw(beat=101,enable=6,echo_beat=100,echo_enable=6,marker=p.CANARY,check=None,good=700,bad=0,tag=p.SIG):
    if check is None:check=(~(marker^echo_beat^echo_enable))&0xffffffff
    return struct.pack('<12I',beat,enable,900,3,1000,marker,echo_beat,echo_enable,check,good,bad,tag)

def test_dynamic_event_counts_pass_checksum_and_capture_transport_lag():
    v=p.decode(raw())
    assert v['revision']=='METRO-TAPSYNC-R02B2-AUDIO-PHASE'
    assert v['dsp_echo_integrity_valid']
    assert v['dsp_echo_tap_count']==100 and v['tap_led_on_count']==101
    assert v['tap_count_difference_m4_minus_dsp']==1
    assert v['dsp_echo_enable_count']==v['metro_41c_enable_count']==6
    assert v['dsp_echo_valid_frames']==700 and v['dsp_echo_bad_checksum_frames']==0


def test_ambiguous_marker_or_bad_checksum_does_not_claim_delivery():
    assert not p.decode(raw(marker=0x01234567))['dsp_echo_integrity_valid']
    assert not p.decode(raw(check=0x00000000))['dsp_echo_integrity_valid']


def test_stale_and_wrong_replies_rejected():
    for data in [b'',b'\xc4\x30',raw(tag=0x31423252),raw()[:-4]]:
        with pytest.raises(ValueError):p.decode(data)
