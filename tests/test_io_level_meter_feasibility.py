"""Offline feasibility invariants for a future dual I/O level meter.

No pedal or USB operations; no firmware writes or patching. These checks
pin the real R03C donor layout and keep the proposed virtual setting IDs
from overlapping the existing HXtra configuration.
"""
from pathlib import Path
import hashlib,sys
ROOT=Path(__file__).parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tools/sharc')]
import block3,setting_ids,patch_amp as pa,l6ia
from metro_led_sharc_patch import parse_ldr,initialized_ram

R03C=ROOT/'build/browser-ramrun/METRO-LEDSYNC-R03C-HWGLITCH-REPAIR/METRO-LEDSYNC-R03C-HWGLITCH-REPAIR.hxf'
SHA='42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b'

def test_exact_R03C_dsp_partition_and_existing_source_hooks():
    assert hashlib.sha256(R03C.read_bytes()).hexdigest()==SHA
    archive,yes=pa.load_l6ia_from_any(str(R03C))
    assert yes
    e=l6ia.parse(archive)[2]
    data=archive[e['payload_off']:e['payload_off']+e['payload_len']]
    blocks,_,_=parse_ldr(data)
    dm,_=initialized_ram(blocks)
    assert len(data)==524212 and 524288-len(data)==76
    assert len(blocks)==201
    # Values read from the actual installed image, not just upstream comments.
    expect={0x200005:0xe4f4a, 0x20000d:0x8cdca, 0x200015:0x8cdd2,
            0x20001d:0xe5024,0x200025:0xe4ff6,
            0x20002d:0xe5081,0x200035:0xe5046,0x20037d:0xe4f4d}
    for addr,value in expect.items():
        assert dm.get(addr)==value,(hex(addr),hex(dm.get(addr,0)))

def test_budget_with_same_features_and_two_NAM_slots():
    flags=['HX_CLICK','HX_FX_GATE','HX_GR','HX_USB_MONITOR','HX_GATE_SC']
    env={k:'1' for k in flags}|{'HX_NAM_SLOTS':'2'}
    costs=[block3.cost(k) for k in flags]
    assert costs==[240,291,780,414,324]
    assert sum(costs)==2049 and block3.words(2)==2528
    assert block3.words(2)-sum(costs)==479
    assert block3.slots(env)==2

def test_unallocated_virtual_5bit_thickness_settings_have_no_conflict():
    occupied={e[0] for e in setting_ids.VIRTUAL}
    assert 0xe6 not in occupied and 0xe7 not in occupied
    new=[(0xe6,114,0,5,'io_meter.input_thickness','exploratory only'),
         (0xe7,114,5,5,'io_meter.output_thickness','exploratory only')]
    assert setting_ids.virtual_problems([*setting_ids.VIRTUAL,*new])==[]
    assert max(range(21)) < (1<<5)
