namespace ns {
template <typename T>
T identity(T value) { return value; }
class Widget {
 public:
  int size() const { return impl_.count(); }
 private:
  Impl impl_;
};
}  // namespace ns
int use(ns::Widget &w) { return w.size() + ns::identity<int>(1); }
