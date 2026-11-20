"""METRO-TAPSYNC-R02B3-BPM-RELOCK-DSPMETER: installed HXtra 1.2.1 M4 UI parity.

Earlier tests compared only Entry 3's 792 DSP model schemas, missing the
real installed HXtra's display/menu/footswitch features and 492 renamed browser
model titles. This test compares the real donor, stock and repaired image.
"""
import os
import struct
from pathlib import Path
import pytest
import patch_amp as pa
import hx_smoke

ROOT = Path(__file__).resolve().parent.parent
STOCK=Path.home()/'Downloads/HX_Stomp_v3.80.0_0x103966115.hxf'
DONOR=Path.home()/'Downloads/HXtra_v1.2.1.hxf'
REPAIRED=ROOT/'build/HXStomp380_HXtra121_METRO-TAPSYNC-R02B3-BPM-RELOCK-DSPMETER_RAM.hxf'

@pytest.fixture(scope='module')
def images():
    out={}
    for name,p in [('stock',STOCK),('donor',DONOR),('repair',REPAIRED)]:
        if not p.exists():pytest.skip(f'{name} image missing: {p}')
        all_entries=pa.load_l6ia_from_any(str(p))[0]
        e0=pa.get_entry_swapped(all_entries,0)
        out[name]={'e0':e0,'segs':pa._parse_e0_segments(e0),
                   'models':hx_smoke.entry3_layouts(all_entries)}
    return out


def read(image,va,size=4):
    d=image['e0'];seg=image['segs']
    off=pa._e0_vaddr_to_foff(seg,va,size)
    return d[off:off+size]


def browser_names(image):
    a=pa.e0_device(image['segs'])
    ptr=struct.unpack('<I',read(image,a.TAB2_BASE_PTR))[0]
    n=pa._decode_thumb_movw(read(image,a.TAB2_CNT_INSN))[1]
    names={}
    for i in range(n):
        row=read(image,ptr+44*i,44)
        idx=struct.unpack_from('<I',row,0)[0]
        names[idx]=row[4:20].split(b'\0')[0].decode('latin1')
    return names


def test_all_792_model_parameter_schemas_unchanged(images):
    donor=images['donor']['models'];new=images['repair']['models']
    pars=lambda z:(z[0],[(p['name'],p['type'],p['lo'],p['hi']) for p in z[1]])
    assert len(donor)==len(new)==792
    assert set(donor)==set(new)
    assert all(pars(donor[k])==pars(new[k]) for k in donor)


def test_browser_model_titles_match_installed_donor_not_stock(images):
    names={k:browser_names(x) for k,x in images.items()}
    stock,donor,new=names['stock'],names['donor'],names['repair']
    differences=[k for k in stock if k in donor and stock[k]!=donor[k]]
    assert len(differences)>=490
    assert len(new)==len(donor)==827
    assert new==donor, [(k,donor[k],new.get(k)) for k in donor if donor[k]!=new.get(k)][:10]


def test_installed_ui_and_control_settings_all_present(images):
    for marker in (b'DSP Usage Display',b'Breathing Line',b'FS1 Hold',
                   b'Activate',b'Tap LED'):
        assert marker in images['donor']['e0'],marker
        assert marker in images['repair']['e0'],marker
    assert b'DSP Usage Display' not in images['stock']['e0']


def test_donor_feature_sites_restored(images):
    # Unique call/patch sites, inspected in the actual donor, not guessed from
    # strings that can also appear in stock firmware or other components.
    sites={
        'label_color':0x28dce962,'tuner':0x28dd1656,
        'tap_color':0x28d9bea8,'bpm':0x28d96c44,
        'dsp_meter':0x28d96da0,'long_press':0x28dd1978,
        'preset_color':0x28dd0c44,
        'more_snapshots':0x28d9b5a2,
        'tap_command':0x28d9be92,
    }
    for name,va in sites.items():
        stock=read(images['stock'],va)
        assert read(images['donor'],va)!=stock,f'donor lacks feature {name}'
        assert read(images['repair'],va)!=stock,f'repaired lacks feature {name}'
    # Strongest evidence for Tap Command: its Command Center type-9 label.
    assert read(images['donor'],0x28e3c628+8*9,8).startswith(b'Tap')
    assert read(images['repair'],0x28e3c628+8*9,8).startswith(b'Tap')


def test_only_usb_monitor_is_consciously_excluded_for_sharc_partition_limit(images):
    # Keep this explicit while the R02B3 code does not fit alongside the
    # original donor's USB Monitor DSP. Do not market this as full donor parity.
    addr=0x28df5760
    assert read(images['donor'],addr)!=read(images['stock'],addr)
    assert read(images['repair'],addr)==read(images['stock'],addr)
    assert b'Path A' in images['donor']['e0']
    assert b'Main+Snd' in images['donor']['e0']
    assert b'Main+Snd' not in images['repair']['e0']
