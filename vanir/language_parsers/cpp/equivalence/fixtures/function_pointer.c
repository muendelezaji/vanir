int apply(int (*callback)(int), int value) {
  int (*local)(int) = callback;
  return local(value);
}
