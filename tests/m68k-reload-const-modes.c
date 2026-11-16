/* Issue #18: two equal constant asm inputs of different modes, under
   register pressure.  Reload must not let the HImode load of zero stand in
   for the SImode one: a word load leaves the upper half unchanged.  */
long reload_const_modes(long *values, int count);

long reload_const_modes(long *values, int count)
{
    long a0 = values[0], a1 = values[1], a2 = values[2], a3 = values[3];
    long a4 = values[4], a5 = values[5], a6 = values[6], a7 = values[7];
    long a8 = values[8], a9 = values[9], a10 = values[10], a11 = values[11];
    long total = 0;
    int i;

    for (i = 0; i < count; ++i) {
        long wide = 0, out;
        short narrow = 0;
        /* OUT = WIDE + NARROW + 0x10000, reading WIDE at full width.  */
        __asm__ volatile ("move.l %1,%0\n\tadd.w %2,%0\n\tadd.l #0x10000,%0"
                          : "=&d"(out) : "r"(wide), "r"(narrow)
                          : "d1", "d2", "a0", "a1", "a2", "cc", "memory");
        total += out;
        a0 += a1; a1 += a2; a2 += a3; a3 += a4; a4 += a5; a5 += a6;
        a6 += a7; a7 += a8; a8 += a9; a9 += a10; a10 += a11; a11 += a0;
    }
    values[0] = a0; values[1] = a1; values[2] = a2; values[3] = a3;
    values[4] = a4; values[5] = a5; values[6] = a6; values[7] = a7;
    values[8] = a8; values[9] = a9; values[10] = a10; values[11] = a11;
    return total;
}
