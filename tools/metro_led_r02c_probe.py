#!/usr/bin/env python3
"""Read-only USB 0x50 telemetry from donor-direct METRO-LEDSYNC-R02C.

Counts final filtered FS3 LED dark->lit commands while FS3 is TAP and 41C
Metronome is enabled. The physical optical transition is downstream of the
controller command. The installed original SHARC GR RX does NOT include the
R02B1E diagnostic echo; the echoed fields cannot confirm DSP consumption.
No device configuration changes.
"""
import argparse,contextlib,json,struct,time
import hx_ctl

SIG=0x43324352
CMD=0x50
MARK=0x4d543242


def decode(data):
    if not isinstance(data,bytes) or len(data)!=48:
        raise ValueError('R02C expected 48 bytes, got '+str(len(data)))
    led_on,engage,tx,skipped,rx,marker,dsp_on,dsp_engage,cs,valid,bad,tag=struct.unpack('<12I',data)
    if tag!=SIG:
        raise ValueError(f'R02C wrong RAM revision: 0x{tag:08x}, expected 0x{SIG:08x}')
    echoed=(marker==MARK and cs==((~(marker^dsp_on^dsp_engage))&0xffffffff))
    return dict(revision='METRO-LEDSYNC-R02C-DONOR-EGRESS',
                final_fs3_led_on_event_counter=led_on, # high bit toggles once on re-enable's first flash
                final_led_on_count_low31=led_on&0x7fffffff,
                phase_reset_marker_bit=bool(led_on&0x80000000),
                metronome_slot8_engage_count=engage,
                m4_spi_frames_stamped=tx,m4_spi_frames_unstamped=skipped,
                donor_gr_rx_frames=rx,
                sharc_echo_diagnostic_available=echoed,
                sharc_echo_data_if_any={'marker':f'0x{marker:08x}','LED_event':dsp_on,
                    'engage':dsp_engage,'checksum':f'0x{cs:08x}',
                    'good_frames':valid,'bad_frames':bad} if echoed else None,
                optical_led_transition_directly_measured=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--samples',type=int,default=8)
    p.add_argument('--interval',type=float,default=.4)
    p.add_argument('--out')
    a=p.parse_args()
    if not 1<=a.samples<=300 or not 0<=a.interval<=30:p.error('samples 1..300, interval 0..30')
    with hx_ctl.HxCtl(timeout=3) as c:
        with (open(a.out,'w') if a.out else contextlib.nullcontext()) as out:
            for i in range(a.samples):
                row={'sample':i,'host_monotonic':time.monotonic(),**decode(c.ed.request(CMD,timeout=4))}
                line=json.dumps(row)
                print(line,flush=True)
                if out:out.write(line+'\n');out.flush()
                if i+1<a.samples:time.sleep(a.interval)
if __name__=='__main__':main()
