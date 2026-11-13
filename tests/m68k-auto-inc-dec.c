/* Issue #15: the source register also occurs in the destination address.
   Keep this translation unit separate from the runtime check. */
#define COPY(name, type, first, condition, step) \
void name(unsigned long destination, unsigned long source) \
{ \
    volatile type *d = (void *)(destination + 0x80000000UL); \
    volatile type *s = (void *)(source + 0x80000000UL); \
    unsigned int i; \
    for (i = first; condition; i step) \
        d[i] = s[i]; \
}

COPY(copy_long, unsigned long, 64, i < 128, ++)
COPY(copy_word, unsigned short, 64, i < 128, ++)
COPY(copy_byte, unsigned char, 64, i < 128, ++)
COPY(copy_float, float, 64, i < 128, ++)
COPY(copy_long_backwards, unsigned long, 127, i > 63, --)
COPY(copy_word_backwards, unsigned short, 127, i > 63, --)
COPY(copy_byte_backwards, unsigned char, 127, i > 63, --)
COPY(copy_float_backwards, float, 127, i > 63, --)
