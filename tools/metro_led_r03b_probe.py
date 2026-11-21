#!/usr/bin/env python3
"""R03B read-only editor query for live M4 LED-master sender integrity.

The sender uses 32-bit LED-event count at M4 SPI TX 240 plus complement at
241. That pair is *readable* through this M4-side diagnostic, but this does
not prove it was actually received by SHARC or that optical flashes and
audio samples are temporally aligned. Only physical listening/capture does.
"""
import argparse,contextlib,json,struct,time
VARIANT='METRO-LEDSYNC-R03B-LED-MASTER'
SIGNATURE=0x31423352 # R3B1
CMD=0x50

def decode(data):
    if not isinstance(data,bytes) or len(data)!=48:
        raise ValueError(f'{VARIANT}: expected 48 bytes, got {len(data)}')
    counts=struct.unpack('<12I',data)
    if counts[11]!=SIGNATURE:
        raise ValueError(f'{VARIANT}: wrong diagnostic revision 0x{counts[11]:08x}')
    count=counts[0];tx=counts[6];checksum=counts[7]
    return {
      'revision':VARIANT,
      'LED_on_count_low31':count&0x7fffffff,
      'LED_epoch_bit31':bool(count&0x80000000),
      'raw_LED_event_count':count,
      'slot8_Metronome_engage_transitions':counts[1],
      'SPI_tx_frames_stamped':counts[2],
      'SPI_tx_frames_skipped':counts[3],
      'short_dark_reversals_filtered':counts[4],
      'SPI_tx_frames_no_TAP_or_LED_hidden':counts[5],
      'last_M4_TX_word240_event':tx,
      'last_M4_TX_word241_checksum':checksum,
      'last_M4_TX_pair_is_valid':checksum==((~tx)&0xffffffff),
      'M4_packet_is_current_as_of_query':tx==count,
      'SHARC_consumption_measured':False,
      'optical_LED_or_audio_latency_measured':False,
    }

def main():
    import hx_ctl
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--samples',type=int,default=30)
    p.add_argument('--interval',type=float,default=.25)
    p.add_argument('--out')
    a=p.parse_args()
    if not 1<=a.samples<=1200 or not .05<=a.interval<=30:p.error('samples 1..1200, interval .05..30')
    with hx_ctl.HxCtl(timeout=3) as ctl:
        with (open(a.out,'w') if a.out else contextlib.nullcontext()) as f:
            for i in range(a.samples):
                row={'sample':i,'host_monotonic_s':time.monotonic()}
                try:row.update(decode(ctl.ed.request(CMD,timeout=4)))
                except ValueError as e:row['invalid_sample']=str(e)
                line=json.dumps(row)
                print(line,flush=True)
                if f:f.write(line+'\n');f.flush()
                if i+1<a.samples:time.sleep(a.interval)
if __name__=='__main__':main()
