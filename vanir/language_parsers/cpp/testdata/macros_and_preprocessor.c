#include <stdio.h>
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#ifdef FEATURE_X
int feature(void) { return MAX(1, 2); }
#else
int feature(void) { return 0; }
#endif
