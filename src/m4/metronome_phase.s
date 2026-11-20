@ Experimental 41C metronome TAP phase transport over a proven M4->SHARC path.
@ Carries a nonpersistent, encoded USB Input Trim value via the stock app
@ parameter setter; the SHARC wrapper decodes it and restores the real trim.
@ Does NOT alter SPI framing or stored preset data. See tools/patch_metro_phase.py.
.syntax unified
.thumb
.equ PARAM_FIND, 0x28df35a1
.equ PARAM_SEND, 0x28df35e9
.equ GET_VALUE, 0x28e1f845
.equ FS_STATE, 0x28d9607d
.equ TRIM_NAME, 4209
.equ TRIM_ID, 3
.equ METRO_SLOT_41C, 8              @ 41C path A slot 7 is DSP grid position 8
.equ BEAT_CODE, 4096
.equ RESUME_CODE, 5120

.thumb_func
.global mp_output
mp_output:                         @ owns 0x28df5760(ctx,app,path,value), r12 stock
    push {r4-r8, lr}
    mov r4, r0
    mov r5, r1
    mov r6, r2
    mov r8, r12
    blx r8
    mov r7, r0
    cmp r7, #0
    blt mp_output_done
    cbnz r6, mp_output_done
    cbz r4, mp_output_done
    cbz r5, mp_output_done
    adr.w r3, mp_cache
    str r4, [r3]
    str r5, [r3, #4]
mp_output_done:
    mov r0, r7
    pop {r4-r8, pc}

.thumb_func
.global mp_beat
mp_beat:                           @ replaces FS_STATE call at stock TAP LED's ON transition
    push {r4, lr}
    ldr r3, =FS_STATE
    blx r3
    mov r4, r0
    movs r0, #0                   @ TAP phase pulse
    bl mp_emit
    mov r0, r4                    @ preserve original FS_STATE result
    pop {r4, pc}

.thumb_func
.global mp_bypass
mp_bypass:                         @ called AFTER the stock bypass setter (r0=engine,r1=slot,r2=bypassed)
    cmp r1, #METRO_SLOT_41C       @ diagnostic target 41C only; general model lookup is future work
    bne mp_bypass_done
    cmp r2, #0                    @ 0=enabled, 1=bypassed
    bne mp_bypass_done
    push {r4, lr}
    movs r0, #1                   @ metronome reenabled
    bl mp_emit
    pop {r4, pc}
mp_bypass_done:
    bx lr

mp_emit:                           @ r0 kind: 0 TAP beat, 1 block re-enabled
    push {r4-r7, lr}
    sub sp, #20                   @ param {u8 type,u32 float}, handle and trim records
    mov r7, r0
    adr.w r6, mp_cache
    ldr r4, [r6]                  @ context from the last valid path A output send
    ldr r5, [r6, #4]              @ app, refreshed on preset load
    cbz r4, mp_emit_done
    cbz r5, mp_emit_done
    ldr r4, [r4, #0xc]
    adds r4, #4                   @ stock parameter context
    ldr.w r5, [r5, #0xac8]        @ app instance
    cbz r5, mp_emit_done
    mov r0, r4
    mov r1, r5
    movw r2, #TRIM_NAME
    add r3, sp, #8
    ldr r6, =PARAM_FIND
    blx r6
    cmp r0, #0
    blt mp_emit_done
    movs r0, #TRIM_ID
    add r1, sp, #12
    ldr r6, =GET_VALUE
    blx r6
    cmp r0, #0
    bge mp_trim_ready
    movs r0, #3                   @ float type when trim is unavailable
    str r0, [sp, #12]
    movs r0, #0                   @ 0.0 dB
    str r0, [sp, #16]
mp_trim_ready:
    adr.w r6, mp_cache
    ldrb r0, [r6, #8]
    eor r0, r0, #1
    strb r0, [r6, #8]
    lsls r0, r0, #8               @ alternates +0 / +256, so repeated events reach DSP
    cmp r7, #0
    ite eq
    moveq r1, #BEAT_CODE
    movne r1, #RESUME_CODE
    adds r0, r0, r1
    vmov s0, r0
    vcvt.f32.s32 s0, s0
    vldr s1, [sp, #16]
    vadd.f32 s0, s0, s1           @ encode without changing the real gain
    vstr s0, [sp, #4]
    ldr r1, [sp, #12]
    strb r1, [sp]
    mov r0, r4
    mov r1, r5
    ldr r2, [sp, #8]
    mov r3, sp
    ldr r6, =PARAM_SEND
    blx r6
mp_emit_done:
    add sp, #20
    pop {r4-r7, pc}

.align 2
mp_cache:
    .word 0, 0                    @ ctx, app; populated on successful path-A send
    .word 0                       @ event parity bit
.ltorg
