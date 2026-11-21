# METRO-LEDSYNC-R03C-HWGLITCH-REPAIR

RAM-only revision for the two SHARC event bugs reproduced after user HWGLITCH01
on R03B: backward accepted counts and intermittent no-TAP native fallback.

- Donor HXF SHA256: `96ac133e094c75f2701226fc7cf3fca4c04b19b91aa34785e646d919979b88c0`.
- R03C candidate HXF SHA256: `42c7bf82a5b0ce478aeedd4d6b8ca27c30cc87680ca2a84473613759cf68ba8b`.
- Four original M4 hooks, one original 142-word SHARC record; 201 LDR
  descriptors intact and Entry2 size 524212 bytes.
- Four RAM-only overlay sectors including metadata sector 0x8802.
- Full 32-bit complement validation; monotone low31 event guard.
- 4600 SPI-frame noTAP grace; known persistent mode switch reverts
  to native Time behavior. 20ms LED dark reversal filter unchanged.
- Extended 84-byte read-only M4 diagnostic 0x50 including actual
  accepted LED command to first M4 TX callback delay in microseconds.
- **No measured SHARC/audio or optical latency; acoustic lag NOT fixed.**
- 100% user-initiated experimental RAM transfer. No permanent eMMC writes.
- `tools/metro_led_r03c_probe.py` for read-only post-boot counters.
