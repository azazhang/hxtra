"""Inherited METRO-TAPSYNC-R02A-M4EDGE edge hooks retested in R02B1 image.

Confirms that the TAP LED callback and bypass hook only touch aligned u32
counters, leave app/system locks untouched, preserve the stock return, and
that the read-only editor command returns those counters as msgpack binary.
This does not substitute for live scheduler/hardware timing verification.
"""
import os
import struct
import tempfile

import pytest
import m4asm
import usb_commands
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_SP, UC_ARM_REG_LR
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5,
                               UC_ARM_REG_R12)

BASE = 0x28e70000
STOP = 0x28001000
FS_STATE = 0x28d9607c
REPLY_SEND = 0x28e15b30
REGISTER = 0x28e165f0


@pytest.fixture(scope='module')
def assembled():
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, 'usb.inc'), 'w') as f:
            f.write(usb_commands.inc('metronome_phase'))
        return m4asm.assemble_module('src/m4/metronome_phase.s', include=(d,))


class Machine:
    def __init__(self, assembled):
        code, self.sym = assembled
        self.code = code
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
        self.uc.mem_map(0x28000000, 0x1000000)  # 16 MiB M4 firmware/SDRAM
        self.uc.mem_map(0x20000000, 0x10000)  # Cortex-M4 stack and request
        self.uc.mem_write(BASE, code)
        self.uc.mem_write(STOP, b'\x00\xbf')  # NOP; hook stops before it
        self.uc.reg_write(UC_ARM_REG_SP, 0x2000f000)
        self.callbacks = []
        self.sent = None
        self.registered = None
        self.uc.hook_add(UC_HOOK_CODE, self.on_code)

    def on_code(self, uc, address, size, user_data):
        if address == STOP:
            uc.emu_stop()
        elif address == FS_STATE:
            self.callbacks.append('fs_state')
            uc.reg_write(UC_ARM_REG_R0, 42)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR) | 1)
        elif address == REGISTER:
            self.callbacks.append('register')
            command = uc.reg_read(UC_ARM_REG_R0)
            argp = uc.reg_read(UC_ARM_REG_R1)
            self.registered = (command, struct.unpack('<3I', uc.mem_read(argp, 12)))
            uc.reg_write(UC_ARM_REG_R0, 0)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR) | 1)
        elif address == REPLY_SEND:
            self.callbacks.append('reply_send')
            stream = uc.reg_read(UC_ARM_REG_R0)
            seq = uc.reg_read(UC_ARM_REG_R1)
            status = uc.reg_read(UC_ARM_REG_R2)
            ptr = uc.reg_read(UC_ARM_REG_R3)
            sp = uc.reg_read(UC_ARM_REG_SP)
            length, = struct.unpack('<I', uc.mem_read(sp, 4))
            self.sent = (stream, seq, status, bytes(uc.mem_read(ptr, length)))
            uc.reg_write(UC_ARM_REG_R0, 0)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR) | 1)

    def call(self, name, r0=0, r1=0, r2=0, r3=0):
        uc = self.uc
        for reg, val in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3),
                            (r0, r1, r2, r3)):
            uc.reg_write(reg, val)
        uc.reg_write(UC_ARM_REG_LR, STOP | 1)
        uc.emu_start(BASE + self.sym[name] | 1, STOP, count=5000)
        assert uc.reg_read(UC_ARM_REG_PC) == STOP
        return uc.reg_read(UC_ARM_REG_R0)

    def counters(self):
        addr = BASE + self.sym['mp_counters']
        return struct.unpack('<12I', self.uc.mem_read(addr, 48))


def test_beat_hook_only_calls_original_stock_getter(assembled):
    m = Machine(assembled)
    for n in range(1, 5):
        assert m.call('mp_beat', r0=99, r1=66, r2=55) == 42
        assert m.counters()[:2] == (n, 0)
    assert m.callbacks == ['fs_state'] * 4


def test_bypass_hook_filters_slot_and_state(assembled):
    m = Machine(assembled)
    m.call('mp_bypass', r0=1, r1=7, r2=0)
    m.call('mp_bypass', r0=1, r1=8, r2=1)
    assert m.counters()[1] == 0
    m.call('mp_bypass', r0=1, r1=8, r2=0)
    m.call('mp_bypass', r0=1, r1=8, r2=0)
    assert m.counters()[1] == 2
    assert m.callbacks == []  # zero runtime calls from the bypass handler


def test_usb_command_reports_binary_snapshot(assembled):
    m = Machine(assembled)
    for _ in range(3):
        m.call('mp_beat')
    m.call('mp_bypass', r1=8, r2=0)
    m.call('mp_register')
    assert m.registered[0] == 0x50
    request = 0x20001000
    m.uc.mem_write(request + 0xc, struct.pack('<H', 0x1234))
    m.call('mp_command', r0=0x20002000, r1=request)
    assert m.sent[:3] == (0x20002000, 0x1234, 0)
    assert m.sent[3][:2] == b'\xc4\x30'
    values=struct.unpack('<12I',m.sent[3][2:])
    assert values[:2] == (3, 1) and values[-1]==0x33423252


def test_there_are_no_fpu_or_lock_api_calls_in_realtime_hooks(assembled):
    data, syms = assembled
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    ranges = [('mp_beat', 'mp_bypass'), ('mp_bypass', 'mp_register')]
    for start, end in ranges:
        code = data[syms[start]:syms[end]]
        ins = list(md.disasm(code, BASE + syms[start]))
        assert ins and sum(x.size for x in ins) == len(code)
        for x in ins:
            assert not x.mnemonic.startswith(('v', 'cdp', 'mcr', 'mrc')), x
            assert x.mnemonic not in ('svc','bkpt'), x
            assert '0x28e24c00' not in x.op_str
    assert data[syms['mp_counters']:syms['mp_counters']+8] == bytes(8)
