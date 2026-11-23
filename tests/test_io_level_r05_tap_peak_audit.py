"""Pure offline tests: detect native gaps separately from M4-bar and alternate-key gaps."""
from io_level_r05_tap_peak_audit import summarize

def x(t,led,v1,v2,px,c1,c2):
    return {'time_s':t,'led_count':led,'output1_last':v1,'output2_last':v2,'output_bar_pixels':px,
            'output1_events':c1,'output2_events':c2,'native_nonempty_packets':int(t*40),
            'bar_state_changes':int(t*20),'metronome_transport_active':True}

def test_fully_observed_and_missing_beats_distinguished_with_paint_not_inferred():
    a=[x(0,1,-70,-70,29,1,1),x(.2,2,-70,-70,29,2,2),x(.3,2,-12,-12,114,3,3),x(.6,3,-70,-70,29,4,4),
       x(.7,3,-68,-68,31,5,5),x(1.1,4,-70,-70,29,6,6)]
    d=summarize(a)
    assert d['complete_tap_intervals']==2
    assert (d['output1_high_intervals'],d['output2_high_intervals'],d['M4_packed_bar_high_intervals'])==(1,1,1)
    assert d['per_beat'][0]['out1_detected'] and not d['per_beat'][1]['out1_detected']
    assert d['actual_LCD_paints_measured'] is False and d['physical_sound_observed'] is False

def test_companion_key_can_theoretically_recover_missed_primary_but_not_if_identical():
    r=[x(0,1,-70,-70,29,0,0),x(.5,2,-70,-70,29,1,1),x(.6,2,-68,-12,31,2,2),
       x(1,3,-70,-70,29,3,3),x(1.1,3,-12,-12,114,4,4),x(1.5,4,-70,-70,29,5,5)]
    d=summarize(r)
    assert d['output1_high_intervals']==1 and d['output2_high_intervals']==2
    assert d['either_output_key_high_intervals']==2
    assert d['M4_packed_bar_high_intervals']==1

def test_no_LED_changes_has_no_complete_beats():
    r=[x(0,1,-70,-70,29,0,0),x(.1,1,-12,-12,114,1,1)]
    d=summarize(r)
    assert d['complete_tap_intervals']==0
