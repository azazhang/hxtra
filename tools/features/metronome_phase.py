"""METRO-TAPSYNC-R02B2-AUDIO-PHASE: M4-to-SHARC event driven click.

HX_METRO_SPI_PHASE=1. R02A integer-only event callbacks retained.
A hooked M4 TX frame callback writes a canary and two event counters to
reserved tail words of small SPI frames. The SHARC mirrors four words
back, including the integrity check. The SHARC click kernel uses these events to phase-align quarter-note clicks.
"""
import usb_commands

FLAG = 'HX_METRO_SPI_PHASE'
MENU = False
WEB = False

BEAT_ON_CALL, FS_STATE = 0x28d9be92, 0x28d9607c
BYPASS, BYPASS_STOCK = 0x28e045a0, bytes.fromhex('2de9 f041')
REGISTER_ALL_CALL, REGISTER_ALL = 0x28d96adc, 0x28e1661c
TX_CB_LIT, TX_CB = 0x28da6138, 0x10000e95
RX_CB_LIT, RX_CB = 0x28da6134, 0x10001095


def apply(p):
    m = p.module('src/m4/metronome_phase.s', inc={'usb.inc': usb_commands.inc('metronome_phase')})
    p.own_call(BEAT_ON_CALL, FS_STATE, 'R02B1 TAP LED on-beat event (increment only)', m['mp_beat'])
    p.chain_entry(BYPASS, BYPASS_STOCK, after=m['mp_bypass'])
    p.chain_bl(REGISTER_ALL_CALL, REGISTER_ALL, after=m['mp_register'])
    p.chain_ptr(TX_CB_LIT, TX_CB, after=m['mp_tx_stamp'])
    p.chain_ptr(RX_CB_LIT, RX_CB, before=m['mp_rx_probe'])
