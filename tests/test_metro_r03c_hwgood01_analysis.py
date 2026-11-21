"""R03C HWGOOD01: immutable physical LED-to-first-M4-TX timing trace QA."""
import json,hashlib,pytest
from pathlib import Path
from analyze_metro_r03c_hwgood01 import analyze,DEFAULT,percent

def test_R03C_real_hardware_23_event_delay_distribution():
    x=analyze()
    assert x['hardware_test']=='HWGOOD01'
    assert x['raw_readonly_USB_0x50_samples']==80
    assert x['distinct_hardware_led_event_count']==23
    assert x['first_event_raw_u32']==2147484490
    assert x['last_event_raw_u32']==2147484512
    x=x['M4_LED_command_to_first_M4_SPI_TX_callback_us']
    assert x['count']==23
    assert x['min']==39
    assert x['median']==165
    assert x['max']==419
    assert x['mean']==pytest.approx(225.304347826)
    assert x['p95_linear_interpolated']==pytest.approx(408.2)
    assert percent(x['per_distinct_event'],.95)==pytest.approx(408.2)

def test_R03C_real_stable_100BPM_and_zero_packet_errors():
    x=analyze()
    assert x['M4_postfilter_LED_ON_to_ON_intervals_us']['count']==22
    assert x['M4_postfilter_LED_ON_to_ON_intervals_us']['median_equivalent_BPM']==pytest.approx(100,abs=.05)
    assert x['all_reported_M4_TX_pairs_consistent']
    assert x['all_reported_M4_TX_counts_current']
    for v in x['cumulative_interruptions_during_query'].values():
        assert v['increase']==0

def test_HWGOOD01_summary_matches_raw_and_discloses_unmeasured_physical_latency():
    x=analyze()
    p=Path('tests/hardware_evidence/METRO-LEDSYNC-R03C-HWGOOD01-LEDTX-TIMING-ANALYSIS-20261120.json')
    reported=json.loads(p.read_text())
    assert reported==x
    assert reported['source_sha256']==hashlib.sha256(DEFAULT.read_bytes()).hexdigest()
    assert not reported['physical_acoustic_click_latency_measured']
    assert not reported['optical_LED_latency_measured']
    assert 'BEFORE' in reported['timing_origin']
    assert 'BEFORE actual SPI physical transfer' in reported['timing_destination']
