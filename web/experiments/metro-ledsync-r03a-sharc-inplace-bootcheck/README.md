# METRO-LEDSYNC-R03A-SHARC-INPLACE-BOOTCHECK

SHARC-only original-boot-record topology test. No M4 change, no enabled LED
transport. All exact installed donor features retained. The user decides
whether to run this RAM-only image.

* Exact donor L6IA entries changed: [2] only.
* Entry2 original / new size: 524212 / 524212 bytes.
* Original LDR records: 201, unchanged size/order/location/descriptor topology.
* Only mutated LDR record: #177, 142 PM instructions at 0xe5386.
* RAM hook overlays exactly sector 0x8802 plus one modified PM payload
  sector and one padded unchanged final partial payload sector.
* eMMC writing: RAM redirect only.
* DSP audio equivalence for valid settings: checked in ssim.
* LED packet: exploratory, incomplete CRC; no M4 sender in this boot check.
* Physical boot: awaiting user test.
* Build and plan: `tools/stage_metro_led_r03a_inplace.py`.
* Tests: `tests/test_metro_led_r03a_inplace.py` and `tests/test_metro_led_r03a_bootplan.py`.
