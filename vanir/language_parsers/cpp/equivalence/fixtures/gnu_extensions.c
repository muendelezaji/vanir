struct item { int value; };
static inline int __attribute__((unused)) read_item(struct item *item) {
  typeof(item->value) result = item->value;
  asm volatile ("" : "+r" (result));
  return result;
}
