"""METRO-TAPSYNC-R02A-M4EDGE: bounded TAP/bypass M4 diagnostic, no DSP calls.

HX_METRO_EDGE_DIAG=1. Feature stores only integer counters from realtime
callbacks; a separate read-only command (USB editor 0x50) returns the counters.
It deliberately does not claim to synchronize SHARC audio in this revision.
"""
import usb_commands

FLAG = 'HX_METRO_EDGE_DIAG'
MENU = False
WEB = False

BEAT_ON_CALL, FS_STATE = 0x28d9be92, 0x28d9607c
BYPASS, BYPASS_STOCK = 0x28e045a0, bytes.fromhex('2de9 f041')
REGISTER_ALL_CALL, REGISTER_ALL = 0x28d96adc, 0x28e1661c


def apply(p):
    m = p.module('src/m4/metronome_phase.s', inc={'usb.inc': usb_commands.inc('metronome_phase')})
    p.own_call(BEAT_ON_CALL, FS_STATE, 'R02A TAP LED on-beat event (increment only)', m['mp_beat'])
    p.chain_entry(BYPASS, BYPASS_STOCK, after=m['mp_bypass'])
    p.chain_bl(REGISTER_ALL_CALL, REGISTER_ALL, after=m['mp_register'])
