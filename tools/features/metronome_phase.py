"""Experimental 41C TAP/metronome bypass phase signalling (M4 to SHARC).

Proven carrier: usbInGain0_1 app parameter sent through PARAM_SEND, decoded
on SHARC by a Level gain control wrapper. This diagnostic targets bypass of
41C path A slot 7 (grid position 8). Do not ship as general preset support.
"""
import patch_menu as pm

FLAG = 'HX_METRO_PHASE'
MENU = False
WEB = False
CONFLICTS = ('tap_command', 'usb_monitor')

OUTPUT = 0x28df5760
OUTPUT_STOCK = bytes.fromhex('f0b5 85b0')
BEAT_ON_CALL = 0x28d9be92
FS_STATE = 0x28d9607c
BYPASS = 0x28e045a0
BYPASS_STOCK = bytes.fromhex('2de9 f041')


def apply(p):
    raise SystemExit("HX_METRO_PHASE quarantined: M4 UI freeze on BPM adjustment."
                     " Do not enable until LED callback's FPU/locking calls are redesigned.")
    m = p.module('src/m4/metronome_phase.s')
    h = p.own_entry(OUTPUT, OUTPUT_STOCK, 'M4 app output sender; save valid app context')
    a = pm.Asm(p.next())
    a.movw_movt(12, h.stock | 1)
    a.bw(m['mp_output'])
    h.to(p.add(a.bytes()))
    p.own_call(BEAT_ON_CALL, FS_STATE, 'stock TAP LED ON beat', m['mp_beat'])
    p.chain_entry(BYPASS, BYPASS_STOCK, after=m['mp_bypass'])
