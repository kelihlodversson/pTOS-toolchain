/* Freestanding Linux/m68k executable: no pTOS or Linux C library needed. */
#define CHECK(name, type) \
extern void name(unsigned long, unsigned long); \
static int check_##name(void) \
{ \
    type source[160], destination[160]; \
    unsigned int i; \
    for (i = 0; i < 160; ++i) { \
        source[i] = (type)(i * 17 + 3); \
        destination[i] = (type)0xa5; \
    } \
    name((unsigned long)destination - 0x80000000UL, \
         (unsigned long)source - 0x80000000UL); \
    for (i = 0; i < 160; ++i) { \
        if (source[i] != (type)(i * 17 + 3)) return 1; \
        if (destination[i] != (i >= 64 && i < 128 ? source[i] : (type)0xa5)) \
            return 1; \
    } \
    return 0; \
}

CHECK(copy_long, unsigned long)
CHECK(copy_word, unsigned short)
CHECK(copy_byte, unsigned char)
CHECK(copy_long_backwards, unsigned long)
CHECK(copy_word_backwards, unsigned short)
CHECK(copy_byte_backwards, unsigned char)

extern void copy_float(unsigned long, unsigned long);
extern void copy_float_backwards(unsigned long, unsigned long);

static int check_float(void (*copy)(unsigned long, unsigned long))
{
    float source[160], destination[160];
    unsigned char *s = (void *)source, *d = (void *)destination;
    unsigned int i;
    /* Initialize and compare object representations without floating point
       helpers.  Every source value has a finite, normal representation. */
    for (i = 0; i < sizeof source; ++i) {
        s[i] = i % 4 == 0 ? 0x3f : (unsigned char)(i * 17 + 3);
        d[i] = 0;
    }
    copy((unsigned long)destination - 0x80000000UL,
         (unsigned long)source - 0x80000000UL);
    for (i = 0; i < sizeof source; ++i) {
        if (s[i] != (i % 4 == 0 ? 0x3f : (unsigned char)(i * 17 + 3))) return 1;
        if (d[i] != (i >= 256 && i < 512 ? s[i] : 0)) return 1;
    }
    return 0;
}

int main(void)
{
    return check_copy_long() || check_copy_word() || check_copy_byte()
        || check_copy_long_backwards() || check_copy_word_backwards()
        || check_copy_byte_backwards()
        || check_float(copy_float) || check_float(copy_float_backwards);
}

__asm__(".text\n"
        ".globl _start\n"
        "_start:\n"
        "jsr main\n"
        "move.l %d0,%d1\n"
        "moveq #1,%d0\n"
        "trap #0\n");
