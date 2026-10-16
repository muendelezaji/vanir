class Counter {
 public:
  int value() const { return stored; }
  void set(int value) { stored = value; }
 private:
  int stored;
};
int CounterValue(int value) { return value; }
