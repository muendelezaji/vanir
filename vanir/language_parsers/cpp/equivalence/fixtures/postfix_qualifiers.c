int const retain(int const value) {
  int volatile local = value;
  return local;
}
