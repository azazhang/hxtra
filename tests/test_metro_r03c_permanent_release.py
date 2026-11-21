"""QA01 regression: updater-ready R03C is the physically booted original HXF.

These tests are offline and never touch the HX Stomp or invoke Line6 Updater.
"""
from pathlib import Path
import json,hashlib
from audit_metro_r03c_permanent_hxf import audit,CAND,DONOR

ROOT=Path(__file__).parents[1]
MANIFEST=ROOT/'tests/hardware_evidence/METRO-LEDSYNC-R03C-HWGOOD01-UPDATER-QA01-20261120.json'

def test_updater_HXF_integrity_pins_exact_user_tested_binary():
    result=audit()
    m=json.loads(MANIFEST.read_text())
    assert result['candidate_SHA256']==m['candidate_sha256']
    assert result['size_bytes']==m['candidate_byte_length']==45860002
    assert result['donor_SHA256']==m['donor_HXtra_sha256']
    assert result['modified_entries']==[0,2]
    assert result['bootloader_entry1_unchanged']
    assert result['other_13_entries_unchanged']
    assert result['P36Updater_trailer_byte_identical']
    assert result['P36Updater_trailer_bytes_original']==101392
    assert result['HXF_FORM_size_correct'] and result['hxf_MD5_correct']
    assert result['Updater_dinf_ranges_valid']
    assert result['SHARC_LDR_201_descriptors_original']
    assert result['SHARC_Entry2_size']==524212
    assert result['SHARC_PM_record_instructions']==142
    assert not result['on_device_Line_6_Updater_executed']

def test_protect_current_R03C_working_tag_and_no_binary_disclosure_in_repo():
    m=json.loads(MANIFEST.read_text())
    assert m['user_confirmed_duplicate_click_resolved']
    assert m['LED_to_audible_click_delay_remaining']
    assert not m['persistently_installed']
    assert not m['actual_Updater_write_tested']
    assert m['upstream_latest_release']=='v1.2.1'
    assert m['R03C_current_builder_rejects_any_donor_except_original_1_2_1_sha']
    assert m['new_upstream_release_requires_new_donor_and_binary_port']
    assert CAND.read_bytes()[:4]==b'FORM'
    assert not (ROOT/'web/experiments/metro-ledsync-r03c-hwglitch-repair/METRO-LEDSYNC-R03C-HWGLITCH-REPAIR.hxf').exists()
    assert hashlib.sha256(DONOR.read_bytes()).hexdigest()==m['donor_HXtra_sha256']
