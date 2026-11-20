// Experimental TAP/enable event receiver. M4 encodes the event in the
// HelixStomp_App USB Input Trim parameter and the Level gains' pid 1 sees it.
// The wrapper restores the true trim before calling the original gain control.
// This is a proven route used by HXtra USB Monitor; only the event protocol is new.
.equ ORIG_CTRL_80, 0x60f3e2
.equ GAIN_PID, 1
.equ CODE_MIN,    0x456AC000      // 3756.0; normal trim is many orders lower
.equ EVENT_SPLIT, 0x45900000      // 4608.0: beat vs re-enable
.equ BEAT_PARITY, 0x45840000      // 4224.0: beat parity 0 vs 1
.equ RESUME_PARITY, 0x45a40000    // 5248.0: resume parity 0 vs 1
.equ EVT_BEAT0, 0x45800000              // 4096.0
.equ EVT_BEAT1, 0x45880000              // 4352.0
.equ EVT_ENABLE0, 0x45a00000              // 5120.0
.equ EVT_ENABLE1, 0x45a80000              // 5376.0

.section dm MP_DM_BASE
MP_EVENT: .space 1

.section pm MP_PM_BASE
MP_CTRL_80:                         // stock gain control sees pid in R4, value pointer in R8
    R2 = GAIN_PID;
    COMP(R4, R2);
    IF NE JUMP ORIG_CTRL_80;
    I4 = R8;
    R0 = DM(0, I4);
    R2 = CODE_MIN;
    COMP(F0, F2);
    IF LE JUMP ORIG_CTRL_80;
    R2 = EVENT_SPLIT;
    COMP(F0, F2);
    IF GT JUMP mp_resume;
    R2 = BEAT_PARITY;
    COMP(F0, F2);
    IF GT JUMP mp_beat_one;
    R1 = 1;
    R2 = EVT_BEAT0;
    JUMP mp_store;
mp_beat_one:
    R1 = 2;
    R2 = EVT_BEAT1;
    JUMP mp_store;
mp_resume:
    R2 = RESUME_PARITY;
    COMP(F0, F2);
    IF GT JUMP mp_resume_one;
    R1 = 3;
    R2 = EVT_ENABLE0;
    JUMP mp_store;
mp_resume_one:
    R1 = 4;
    R2 = EVT_ENABLE1;
mp_store:
    DM(MP_EVENT) = R1;
    F0 = F0 - F2;                    // restore the actual USB input gain trim
    DM(0, I4) = R0;
    JUMP ORIG_CTRL_80;
