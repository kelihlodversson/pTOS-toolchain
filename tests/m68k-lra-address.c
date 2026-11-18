/* pTOS#998: LRA validates a 'p' operand with VOIDmode.  Displacement
      128 must not pass the 68000 signed-byte address check.  The asm printer
      checks the address again with QImode and used to ICE here. */
#ifndef DISPLACEMENT
#define DISPLACEMENT 128
#endif
void use(void *);
void lra_address(unsigned i)
{
    char buf[256];
    void *p;
    __asm__ volatile ("" : "=m" (buf));
    __asm__ volatile ("lea %a1,%0" : "=a" (p) : "p" (&buf[i + DISPLACEMENT]));
    use(p);
}
