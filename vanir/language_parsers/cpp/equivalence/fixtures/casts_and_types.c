int convert(const unsigned long value, void *opaque) {
  const struct record *record = (struct record *)opaque;
  unsigned int count = (unsigned int)value;
  use(record, count);
  return (int)count;
}
