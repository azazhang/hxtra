"""METRO-TAPSYNC-R02B3-BPM-RELOCK-DSPMETER: donor-parity TAP events and SHARC sync.

HX_METRO_SPI_PHASE=1. R02A integer-only event callbacks retained.
A hooked M4 TX frame callback writes a canary and two event counters to
reserved tail words of small SPI frames. The SHARC mirrors four words
back, including the integrity check. The SHARC click kernel uses these events to phase-align quarter-note clicks.
"""
import usb_commands
from features import tap_command

FLAG = 'HX_METRO_SPI_PHASE'
MENU = False
WEB = False
ORDER = 121  # after Tap Command, so its tc_on function can be preserved

BEAT_ON_CALL, FS_STATE = 0x28d9be92, 0x28d9607c
BYPASS, BYPASS_STOCK = 0x28e045a0, bytes.fromhex('2de9 f041')
REGISTER_ALL_CALL, REGISTER_ALL = 0x28d96adc, 0x28e1661c
TX_CB_LIT, TX_CB = 0x28da6138, 0x10000e95
RX_CB_LIT, RX_CB = 0x28da6134, 0x10001095


def apply(p):
    tap = p.modules.get(tap_command.MODULE)
    beat_handler = (tap['tc_on'] | 1) if tap else (FS_STATE | 1)
    inc = usb_commands.inc('metronome_phase') + f'\n.equ METRO_PREV_BEAT, {beat_handler:#x}\n'
    m = p.module('src/m4/metronome_phase.s', inc={'usb.inc': inc})
    p.own_call(BEAT_ON_CALL, FS_STATE, 'R02B3 LED beat event: original Tap Command handler plus counter', m['mp_beat'])
    p.chain_entry(BYPASS, BYPASS_STOCK, after=m['mp_bypass'])
    p.chain_bl(REGISTER_ALL_CALL, REGISTER_ALL, after=m['mp_register'])
    p.chain_ptr(TX_CB_LIT, TX_CB, after=m['mp_tx_stamp'])
    p.chain_ptr(RX_CB_LIT, RX_CB, before=m['mp_rx_probe'])
