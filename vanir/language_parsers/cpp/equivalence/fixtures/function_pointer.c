long apply(long (*callback)(short), short value) {
  long (*local)(short) = callback;
  return local(value);
}
