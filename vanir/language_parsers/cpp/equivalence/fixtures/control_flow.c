int walk(int *values, int length) {
  int total = 0;
  for (int index = 0; index < length; ++index) {
    if (values[index] < 0)
      continue;
    total += values[index];
  }
  switch (total) {
    case 0: return -1;
    default: return total;
  }
}
