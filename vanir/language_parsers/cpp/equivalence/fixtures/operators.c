unsigned int update(unsigned int value, int shift) {
  value <<= shift;
  value += 0xff;
  if (value != 0 && shift >= 0)
    value = (value >> 1) | (value & 7);
  return value;
}
