int message(int value) {
  /* braces { } and fake_call() inside comments are not syntax. */
  const char *text = "A\nB\"C";
  char marker = 'X'; // comment after a declaration
  log_message(text, marker);
  return value + 0x10 + 1;
}
