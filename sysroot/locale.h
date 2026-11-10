#ifndef PTOS_LOCALE_H
#define PTOS_LOCALE_H

/* Declaration for libcmini's setlocale shim. */
#define LC_CTYPE    0
#define LC_NUMERIC  1
#define LC_TIME     2
#define LC_COLLATE  3
#define LC_MONETARY 4
#define LC_MESSAGES 5
#define LC_ALL      6

char *setlocale(int category, const char *locale);

#endif
