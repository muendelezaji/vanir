static int (*handler)(int, char *);
int sum(const int *values, unsigned long n, int matrix[][4]) {
  int total = 0;
  char *names[8];
  for (unsigned long i = 0; i < n; i++) {
    total += values[i];
  }
  return total;
}
