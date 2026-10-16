
      /* This code is for testing Vanir Parser. */ int test_globalvar = 10;
      int test_func1(const unsigned int64 test_arg) {
        const struct teststruct *testvar = (struct teststruct *)globalvar->data;
        test_func2(test_arg, testvar);  // some comment.
        /* additional comment line. */
        0xe8();  // broken code -- won't be counted as func call.
        return 0;
      }
      void test_func_decl(int myarg);
      void test_func_def(int myarg) {}
      
