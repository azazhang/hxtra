"""R03C HWFLASH01 immutable read-only post-updater evidence validation."""
import json,hashlib,statistics
from pathlib import Path
import pytest

ROOT=Path(__file__).parents[1]
DATA=ROOT/'tests/hardware_evidence/METRO-LEDSYNC-R03C-HWFLASH01-UPDATER-POSTBOOT-QA-20261121.json'
LOG=ROOT/'tests/hardware_evidence/METRO-LEDSYNC-R03C-HWFLASH01-30SAMPLES-20261121.jsonl'

def raw():
    return [json.loads(line) for line in LOG.read_text().splitlines() if line.strip()]
def metadata():
    return json.loads(DATA.read_text())

def test_install_completed_and_operational_interfaces_verified_without_claiming_audio():
    x=metadata()
    assert x['updater_ui_completion_title']=='Firmware Update Completed Successfully'
    assert x['updater_completion_screen_observed_readonly']
    assert not x['updater_process_running_after_quit']
    assert x['read_only_editor_status_success']
    assert x['editor_block_count']==8
    assert x['read_only_librarian_preset_names_success']
    assert x['USB_audio']['enumerated']
    assert x['USB_audio']['input_channels']==x['USB_audio']['output_channels']==8
    assert x['M4_running_revision_signature']=='METRO-LEDSYNC-R03C-HWGLITCH-REPAIR'
    assert x['local_firmware_installer_file_sha256_matches_frozen_HWGOOD01']
    assert not x['OLED_DSP_usage_percentages_visually_verified']
    assert not x['HXtra_USB_Monitor_menu_verified']
    assert not x['postflash_audible_click_duplicates_retested']
    assert not x['postflash_physical_cold_power_cycle_independently_verified']

def test_30_USB_samples_exact_hex_checksum_current_events_and_no_new_errors():
    x=metadata();rows=raw()
    assert len(rows)==x['raw_readonly_USB_samples']==30
    assert hashlib.sha256(LOG.read_bytes()).hexdigest()==x['raw_readonly_hardware_probe_sha256']
    assert [r['sample'] for r in rows]==list(range(30))
    assert all(r['revision']==x['M4_running_revision_signature'] for r in rows)
    assert all(r['last_M4_TX_pair_is_valid'] for r in rows)
    assert all(r['last_M4_TX_event_is_current'] for r in rows)
    assert all(r['last_M4_TX_word241_checksum']==((~r['last_M4_TX_word240_event'])&0xffffffff) for r in rows)
    unique={}
    for r in rows:unique.setdefault(r['raw_LED_event_count'],r)
    assert len(unique)==x['unique_LED_events']==12
    assert list(unique)==list(range(x['first_LED_counter_raw_u32'],x['last_LED_counter_raw_u32']+1))
    times=[r['last_M4_LED_request_to_first_SPI_TX_us'] for r in unique.values()]
    assert (min(times),statistics.median(times),max(times))==(86,203,402)
    assert [rows[-1][k]-rows[0][k] for k in
        ('SPI_tx_frames_skipped','short_dark_reversals_filtered',
         'SPI_tx_frames_no_TAP_or_LED_hidden','noTAP_frames_held_through_grace',
         'noTAP_frames_sent_as_explicit_local_fallback','slot8_Metronome_engage_transitions')]==[0]*6
    assert rows[-1]['SPI_tx_frames_stamped']-rows[0]['SPI_tx_frames_stamped']==13954
    ons=[r['last_accepted_M4_LED_on_timestamp_us_u32'] for r in unique.values()]
    intervals=[(b-a)&0xffffffff for a,b in zip(ons,ons[1:])]
    assert 60e6/statistics.median(intervals)==pytest.approx(x['M4_LED_ON_ON_median_implied_BPM'],rel=1e-8)

def test_m4_internal_active_flag_and_editor_bypass_mismatch_is_preserved_as_open():
    x=metadata();rows=raw()
    assert not x['metronome_block']['editor_enabled']
    assert x['M4_active_flag_true_while_Metronome_model_bypassed']
    assert all(r['M4_Metronome_active_flag'] for r in rows)
    assert not x['internal_bypass_flag_discrepancy_functional_audio_effect_confirmed']
    assert not x['full_nonvolatile_partition_readback_performed']
