/* Baseline: globals and prototypes do not become functions. */
int global_limit = 8;
int declared_only(int value);
int add(int left, int right) {
  int result = left + right;
  return result;
}

void notify(int value) {
  emit(value);
}
