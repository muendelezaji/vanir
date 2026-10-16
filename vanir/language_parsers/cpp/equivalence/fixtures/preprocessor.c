#include <stddef.h>
#define LIMIT 8
#define APPLY(value) transform(value)
#if defined(ENABLE_FAST)
int select_value(int value) {
  return APPLY(value);
}
#else
int select_value(int value) {
  return value + LIMIT;
}
#endif
