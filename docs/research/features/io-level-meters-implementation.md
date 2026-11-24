# Input and output peak meters — hardware-tested R12 prototype

A working HX Stomp implementation based on HXtra v1.2.1 and the R03C metronome synchronization modification. Intended for review and eventual integration into HXtra ([upstream issue #116](https://github.com/wisemandenny/hxtra/issues/116)).

- Independent input and Main output sample peak meters in Footswitch (Play) and Signal Chain (Edit) views.
- 16 LED segments per meter, uniform 5 dBFS thresholds from -75 through 0 dBFS.
- Peaks measured on the SHARC in 1,024-sample windows, with a checksum and sequence counter on existing DSP-to-M4 telemetry; M4 peak hold and decay.
- Separate Edit-view position to leave the stock divider, DSP Usage numbers and gain-reduction drawing space available.
- Actual hardware RAM tests followed by a successful permanent installation. 344 selected regression tests passed.

## Source entry points

- [DSP peak acquisition and transport](../../../src/sharc/io_level_r09_direct_peaks.asm)
- [M4 peak receiver and uniform scale](../../../src/m4/io_level_r11_direct_meter.s)
- [Edit-view renderer and guards](../../../src/m4/io_level_r12_edit_view.s)
- [R12 build script](../../../tools/build_io_level_r12_edit_view.py)
- [R12 validation and development notes](io-level-r12-edit-view-peak-meters-20261124.md)

## Scope and limitations

This is a version-specific experimental implementation, not yet a portable HXtra feature toggle. The builder depends on the exact R03C/HXtra v1.2.1 donor and preceding R09–R11 artifacts. The source branch includes the corresponding earlier builders and tests; no proprietary firmware image is distributed here. It must be adapted to the upstream build system before ordinary users can build it from a stock firmware input. The current implementation uses fixed visibility and thickness; configurability and calibration across input/routing modes remain future integration work.

The successful personal installation does not establish compatibility with other HXtra configurations, devices, or firmware releases.
