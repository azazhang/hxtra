"""HX Stomp SHARC→M4 native SPI receive payload, decoded from real R01 frames.

Source of truth:
- flashed R03C M4 stock callback at 0x10001094: halfword-rotates header
  word 1 before extracting its low 16 bits as the number of payload words.
- HW02 (2026-11-23), 500 read-only captured frames: native nonzero
  frames have an envelope of 0x18..., 0x03800110 and five-word float
  records. Validate the size and envelope before claiming a record.
- Raw frame words 2..254 can contain *old* data when the native payload
  count is zero. Never interpret them on empty frames.

Record IDs are left UNNAMED. Their mapping to Input versus Output
blocks has not been determined; a dBFS-sounding float is not enough.
"""
import math
import struct

RX_WORDS = 256
NATIVE_ENVELOPE_KIND = 0x18
NATIVE_ENVELOPE_FLAGS = 0x03800110
PEAK_RECORD_PREFIX = (0, 3)
PEAK_RECORD_FAMILY = 0x00020000

def unswap16(word):
    return ((word >> 16) | (word << 16)) & 0xffffffff

def float32(word):
    return struct.unpack("<f", struct.pack("<I", word))[0]

def parse_frame(w):
    if len(w) != RX_WORDS:
        raise ValueError(f"expected exactly {RX_WORDS} raw words")
    header = unswap16(w[1])
    payload_words = header & 0xffff
    seq0 = (header >> 16) & 0xff
    seq1 = (header >> 24) & 0xff
    info = {
        'native_payload_words': payload_words,
        'native_header_seq0': seq0,
        'native_header_seq1': seq1,
        'native_payload_nonempty': bool(payload_words),
        'native_envelope_verified': False,
        'native_full_records': [],
        'native_unclassified_trailing_words': 0,
    }
    if payload_words == 0:
        return info
    if not 4 <= payload_words <= 253:
        info['native_error'] = 'payload length outside native envelope range'
        return info
    words = [unswap16(x) for x in w[2:2+payload_words]]
    if len(words) != payload_words:
        info['native_error'] = 'incomplete declared native payload'
        return info
    if (words[0] >> 24) != NATIVE_ENVELOPE_KIND or words[1] != NATIVE_ENVELOPE_FLAGS or (words[0] & 0xffff) != (payload_words-2)*4:
        info['native_error'] = 'native envelope type, flags or byte length mismatch'
        return info
    info['native_envelope_verified'] = True
    info['native_packet_identity'] = [f'{v:#010x}' for v in words[:4]]
    rest = words[4:]
    info['native_unclassified_trailing_words'] = len(rest)%5
    for j in range(0, len(rest)//5*5, 5):
        rec = rest[j:j+5]
        if rec[0:2] != list(PEAK_RECORD_PREFIX) or not 0 <= rec[3] <= 65535:
            info['native_error'] = 'unrecognized full five-word record'
            break
        value = float32(rec[4])
        info['native_full_records'].append({
            'record_family': f'{rec[2]:#010x}',
            'channel_id': rec[3],
            'value_raw_hex': f'{rec[4]:#010x}',
            'value_float32': value if math.isfinite(value) else None,
        })
    return info
