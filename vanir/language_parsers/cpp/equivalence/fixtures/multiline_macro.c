#define RETRY(action) do { \
  action; \
} while (0)
int retry_operation(int value) {
  RETRY(consume(value));
  return value;
}
