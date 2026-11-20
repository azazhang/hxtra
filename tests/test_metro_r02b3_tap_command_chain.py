"""METRO-TAPSYNC-R02B3: combine HXtra Tap Command and our M4 beat counter.

Installed HXtra has HX_CC_TAP=1. It previously owned the exact same M4 beat
callsite as R02B2, so restoring the feature must preserve tc_on semantics while
counting the event once. This executes the assembled M4 callback with a fake
previous Tap Command handler and checks a single call and the original result.
"""
import os,tempfile
import m4asm,usb_commands
import pytest
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_R0
from test_metro_r02a_m4edge import Machine

TC_ON=0x28e72000


def test_beat_callback_delegates_to_existing_tap_command_then_counts_once():
    with tempfile.TemporaryDirectory() as d:
        inc=usb_commands.inc('metronome_phase')+f'\n.equ METRO_PREV_BEAT, {TC_ON|1:#x}\n'
        with open(os.path.join(d,'usb.inc'),'w') as f:f.write(inc)
        assembled=m4asm.assemble_module('src/m4/metronome_phase.s',include=(d,))
    m=Machine(assembled)
    m.uc.mem_write(TC_ON,b'\x70\x47') # BX LR, interception bypasses it
    seen=[]
    def cb(u,address,size,_):
        if address==TC_ON:
            seen.append('tc_on')
            u.reg_write(UC_ARM_REG_R0,0x13572468)
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR)|1)
    m.uc.hook_add(UC_HOOK_CODE,cb)
    assert m.call('mp_beat')==0x13572468
    assert seen==['tc_on']
    assert m.counters()[:2]==(1,0)
    assert m.call('mp_beat')==0x13572468
    assert seen==['tc_on','tc_on']
    assert m.counters()[:2]==(2,0)
