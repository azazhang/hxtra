"""SHARC M4 event bridge for HX_METRO_PHASE=1 experimental builds.

Wraps the stock Level gain primitive's control function; recognizes the
reserved high-range trim values emitted by src/m4/metronome_phase.s and
stores event 1/2 (beat) or 3/4 (metronome re-enable) in shared DM.
"""
import os
import argparse
import block3
import patch_amp as pa

FLAG='HX_METRO_PHASE'
ASM=os.path.join(os.path.dirname(os.path.dirname(__file__)),'src/sharc/metronome_phase.asm')
GAIN=0x80
GAIN_PROC=0x8d7f5
GAIN_CTRL=0x60f3e2


def asm_src(dm,pm):
    return open(ASM).read().replace('MP_DM_BASE',hex(dm)).replace('MP_PM_BASE',hex(pm))


def dsp_size():
    ss,_=pa.sasm.assemble(asm_src(0xe4000,0xe5000),'metronome_phase.asm')
    return (sum(len(s.words) for s in ss if s.kind=='dm'),sum(len(s.words) for s in ss if s.kind=='pm'))


def event_word():
    dm,pm=block3.place(FLAG)
    _,sym=pa.sasm.assemble(asm_src(dm,pm),'metronome_phase.asm')
    return sym['MP_EVENT']


def patch_dsp(data, log=print):
    dm,pm=block3.place(FLAG)
    ss,syms=pa.sasm.assemble(asm_src(dm,pm),'metronome_phase.asm')
    entries=pa.l6ia.parse(data)
    e=entries[2]
    old=data[e['payload_off']:e['payload_off']+e['payload_len']]
    ldr=[]
    for sec in ss:
        ldr+=(pa.pack_init_l48 if sec.kind=='pm' else pa.pack_init_l32)(sec.addr,sec.words)
        log(f'[+] metronome event {sec.kind} {sec.addr:#x} count {len(sec.words)}')
    ldr+=pa.wrap_primitive(old,f'{GAIN:#x}:{GAIN_PROC:#x}',GAIN_PROC,(GAIN_CTRL,syms['MP_CTRL_80']))
    out,_,_=pa.l6ia.rebuild_archive(data,{2:pa.l6ia.swap32(pa.inject_sharc_ldr_blocks(old,ldr))})
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('input');ap.add_argument('output');ap.add_argument('--donor')
    a=ap.parse_args()
    data,is_hxf=pa.load_l6ia_from_any(a.input)
    pa.save_l6ia_to_any(patch_dsp(data),a.output,donor_hxf=a.input if is_hxf else a.donor)
    print('[+] wrote',a.output)

if __name__=='__main__':main()
