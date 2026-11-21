"""METRO-LEDSYNC-HWFAIL03-REASSESS: independently reproduced known receiver fault.

Both exact-assembled R02C/R02D SHARC receivers currently accept invalid
integrity words. xfail gates are intentionally explicit; the future fix should
make them pass and then remove xfail. No device access or firmware writes.
"""
import pytest
import test_metro_r02c_sharc_led_egress as r02c
import test_metro_r02d_compact_sharc as r02d


@pytest.mark.parametrize("implementation", [r02c, r02d], ids=["R02C", "R02D"])
@pytest.mark.xfail(strict=True, reason="SHARC LED event receiver ignores complemented-XOR integrity word")
def test_corrupted_spi_event_must_be_rejected_before_any_new_click(implementation):
    c = implementation.kernel(time=.1, accent=4)
    implementation.marker(c, 0)
    c.run(64)
    implementation.marker(c, 1)
    c.sim.wr(implementation.LED_RING + 3, 0xBAD0BAD0)
    c.call()
    assert c.sim.rd(implementation.I0 + 28) == 0, "corrupt event advanced last-accepted LED counter"
    assert c.sim.rd(implementation.I0 + 21) == 0, "corrupt event advanced accented beat position"
