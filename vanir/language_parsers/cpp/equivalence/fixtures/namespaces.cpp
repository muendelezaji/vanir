namespace outer {
namespace inner {
int twice(int value) {
  int result = value * 2;
  sink(result);
  return result;
}
}
}
