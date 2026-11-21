# METRO-LEDSYNC-R03B-LED-MASTER

Physical RAM-only user-driven sync candidate, following boot-tested R03A
SHARC kernel and R01 real M4 LED trace.

- Exact donor SHA256: `96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0`
- Candidate HXF SHA256: `d1c9669734eecd928fbaecc82722b5d69c71ff40c1fcab15a1396d61e9053e6c`
- M4 changed sites: `['0x28d98f78', '0x28e045a0', '0x28d96adc', '0x28da6138']`.
- Original SHARC Entry2 524212 bytes and 201 LDR descriptor topology held.
- Exactly 4 RAM-overlay sectors incl metadata header at eMMC 0x8802.
- Real M4 LED ON before illumination command, validated 2-word complement
  at SHARC. 20ms dark-gap suppression derived from physical trace.
- No M4 or SHARC feature intentionally removed from donor.
- Optical latency/acoustic phase not yet measured; hardware run pending.
- `tools/metro_led_r03b_probe.py`: read-only M4 diagnostic 0x50.
- `tests/test_metro_led_r03b_transport.py`: full Unicorn/ssim integration.
- `tools/build_metro_led_r03b.py`: strict exact-donor packer.
- `tools/metro_led_r03b_ramplan.py`: verified RAM overlay planner.
- No permanent firmware write authorized.
