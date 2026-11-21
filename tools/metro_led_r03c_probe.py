#!/usr/bin/env python3
"""R03C read-only HX editor 0x50 telemetry: short TAP losses and M4 LED->TX lag.

Important: last_LED_to_M4_TX_us is a *measured M4 internal boundary*.
It excludes SPI transfer completion, SHARC execution, audio output buffering
and actual optical FS3 LED electronics. It does not by itself quantify
the user's perceived LED-to-click delay or prove sync.
"""
import argparse,contextlib,json,struct,time
VARIANT='METRO-LEDSYNC-R03C-HWGLITCH-REPAIR'
SIGNATURE=0x31433352
CMD=0x50
DATA_BYTES=84

def decode(data):
    if not isinstance(data,bytes) or len(data)!=DATA_BYTES:
        raise ValueError(f'{VARIANT}: expected {DATA_BYTES} bytes, got {len(data)}')
    w=struct.unpack('<21I',data)
    if w[11]!=SIGNATURE:
        raise ValueError(f'{VARIANT}: wrong firmware revision signature 0x{w[11]:08x}')
    if w[12] not in (0,1) or w[13] not in (0,1) or w[14] not in (0,1) or w[16] not in (0,1):
        raise ValueError(f'{VARIANT}: invalid M4 flag state; mixed or corrupt snapshot')
    return {
      'revision':VARIANT,
      'LED_on_count_low31':w[0]&0x7fffffff,
      'LED_epoch_bit31':bool(w[0]&0x80000000),
      'raw_LED_event_count':w[0],
      'slot8_Metronome_engage_transitions':w[1],
      'SPI_tx_frames_stamped':w[2],
      'SPI_tx_frames_skipped':w[3],
      'short_dark_reversals_filtered':w[4],
      'SPI_tx_frames_no_TAP_or_LED_hidden':w[5],
      'last_M4_TX_word240_event':w[6],
      'last_M4_TX_word241_checksum':w[7],
      'last_M4_TX_pair_is_valid':w[7]==((~w[6])&0xffffffff),
      'last_M4_TX_event_is_current':w[6]==w[0],
      'noTAP_frames_held_through_grace':w[8],
      'noTAP_frames_sent_as_explicit_local_fallback':w[9],
      'nonTAP_consecutive_frame_count_diagnostic':w[10],
      'M4_final_LED_state_lit':bool(w[12]),
      'M4_Metronome_active_flag':bool(w[13]),
      'M4_next_LED_downbeat_pending':bool(w[14]),
      'last_M4_LED_dark_timestamp_us_u32':w[15],
      'last_M4_dark_seen':bool(w[16]),
      'M4_nonTAP_actual_streak':w[17],
      'last_accepted_M4_LED_on_timestamp_us_u32':w[18],
      'last_event_reaching_M4_SPI_tx_count':w[19],
      'last_M4_LED_request_to_first_SPI_TX_us':w[20],
      'M4_latency_measure_valid':w[19]!=0 and w[19]==w[6],
      'SHARC_consumer_counter_measured':False,
      'actual_optical_LED_to_acoustic_click_ms_measured':False,
    }

def main():
    import hx_ctl
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--samples',type=int,default=40)
    ap.add_argument('--interval',type=float,default=.25)
    ap.add_argument('--out')
    args=ap.parse_args()
    if not 1<=args.samples<=1200 or not .05<=args.interval<=30:
        ap.error('samples 1..1200 and interval .05..30')
    with hx_ctl.HxCtl(timeout=3) as ctl:
        with (open(args.out,'w') if args.out else contextlib.nullcontext()) as f:
            for i in range(args.samples):
                row={'sample':i,'host_monotonic_s':time.monotonic()}
                try:row.update(decode(ctl.ed.request(CMD,timeout=4)))
                except ValueError as e:row['invalid_sample']=str(e)
                line=json.dumps(row)
                print(line,flush=True)
                if f:f.write(line+'\n');f.flush()
                if i+1<args.samples:time.sleep(args.interval)
if __name__=='__main__':main()
