/* Freestanding Linux/m68k executable: no pTOS or Linux C library needed. */
extern long reload_const_modes(long *, int);
extern long call_with_dirty_registers(void);

static long values[12];

long run_check(void);

long run_check(void)
{
    return reload_const_modes(values, 8);
}

int main(void)
{
    unsigned int i;
    for (i = 0; i < 12; ++i)
        values[i] = (long)(0x12340000UL * (i + 1) + i);
    /* Each of the eight iterations adds 0x10000 to two zero inputs. */
    return call_with_dirty_registers() != 8L * 0x10000;
}

/* Call run_check with a nonzero upper half in every register it and the
   checked function may use without setting.  Neither call has arguments
   outside C, and both ABIs return in D0. */
__asm__(".text\n"
        ".globl call_with_dirty_registers\n"
        "call_with_dirty_registers:\n"
        "movem.l %d2-%d7/%a2-%a6,-(%sp)\n"
        "move.l #0x5a5a5a5a,%d0\n"
        "move.l %d0,%d1\nmove.l %d0,%d2\nmove.l %d0,%d3\nmove.l %d0,%d4\n"
        "move.l %d0,%d5\nmove.l %d0,%d6\nmove.l %d0,%d7\nmove.l %d0,%a0\n"
        "move.l %d0,%a1\nmove.l %d0,%a2\nmove.l %d0,%a3\nmove.l %d0,%a4\n"
        "move.l %d0,%a5\nmove.l %d0,%a6\n"
        "jsr run_check\n"
        "movem.l (%sp)+,%d2-%d7/%a2-%a6\n"
        "rts\n"
        ".globl _start\n"
        "_start:\n"
        "jsr main\n"
        "move.l %d0,%d1\n"
        "moveq #1,%d0\n"
        "trap #0\n");
