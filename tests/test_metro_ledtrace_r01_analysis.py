"""Reproducible cross-checks for physical R01 HWKNOB01 read-only analysis."""
from pathlib import Path
from analyze_metro_ledtrace_r01 import analyze
RAW=Path(__file__).parents[0]/'hardware_evidence/METRO-LEDSYNC-M4LEDTRACE-R01-HWKNOB01-live.jsonl'

def test_exact_revision_and_sample_integrity():
    result=analyze(RAW)
    assert result['usb_samples']==659
    assert result['invalid_samples']==[]
    assert result['duplicated_record_conflicts']==[]
    assert result['edge_count']==620
    assert result['sequence_range']==[380,999]
    assert result['missing_sequences']==[]
    assert result['nonalternating_adjacent_edges']==[]
    assert result['on_count']==310 and result['off_count']==310

def test_phase_discontinuity_and_near_zero_dark_periods_are_grounded():
    report=analyze(RAW)
    assert len(report['off_to_on_under_20ms'])==6
    assert [e['on_sequence'] for e in report['off_to_on_under_20ms']]==[819,821,823,849,899,919]
    by_seq={e['on_sequence']:e for e in report['off_to_on_under_20ms']}
    assert by_seq[899]['preceding_dark_gap_ms']==1.870
    assert abs(report['first_transition']['phase_discontinuity_vs_old_period_ms']+222.165)<0.03
    assert report['min_on_to_on_ms']==322.836
    assert report['max_on_to_on_ms']==1591.358

def test_all_six_stable_segments_have_submillisecond_phase_residuals():
    report=analyze(RAW)
    stable=report['stable_segments']
    assert len(stable)==6
    assert [x['beats'] for x in stable]==[218,8,10,7,6,31]
    expect=[110.0916,102.9203,93.8921,69.2058,56.2337,164.8387]
    for seg,target in zip(stable,expect):
        assert abs(seg['fitted_bpm']-target)<0.001
        assert seg['rms_phase_residual_ms']<0.4
