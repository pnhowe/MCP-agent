from nullunit import iterate

def test_makedidnothing():
  should_be_true = [
    [ "make: Nothing to be done for 'lint'." ],
    [ "make: Nothing to be done for 'test'." ],

  ]

  should_be_false = [
    [ "make: *** [test] Error 127" ],
    [ "make: /usr/local/plato/setup/setupWizard: Command not found", "Makefile:17: recipe for target 'test' failed", "make: *** [test] Error 127" ],
    [ "linter -i jsl-0.3.0 -a tests/linter.config" ],
    [ "E   ImportError: No module named cinp", "============================================================================= 1 error in 0.07 seconds =============================================================================", "Makefile:41: recipe for target 'test' failed", "make: *** [test] Error 1" ],
    [ "Makefile:10: recipe for target 'lint' failed", "make: *** [lint] Error 1" ],
    [ "dpkg-buildpackage: error: tail of debian/changelog gave error exit status 1", "Makefile:55: recipe for target 'dpkg' failed", "make: *** [dpkg] Error 1" ],
    [ "============================================================================ 1 passed in 0.01 seconds =============================================================================", "make[1]: Leaving directory '/home/peter/Projects/plato/plato-client'" ],
    [ "make[1]: Leaving directory '/home/peter/Projects/plato/plato-client-config'", "make[1]: Entering directory '/home/peter/Projects/plato/plato-client'", "make[1]: Nothing to be done for 'lint'.", "make[1]: Leaving directory '/home/peter/Projects/plato/plato-client'" ],
    [ "WARNING: item \"vendor/github.com/boltdb/bolt/README.md\" not mattched.  type: \"C source, ASCII text, with very long lines\".", "gofmt -l .", "vendor/github.com/codegangsta/cli/command_test.go" ],
    [ " Error running previous command: exit status 2", "exit status 1", "Makefile:45: recipe for target 'test' failed", "make: *** [test] Error 1" ],
    [ "go test -cover", "PASS", "coverage: 86.1% of statements", "ok  	mlx/mlxmetric	0.004s" ],

  ]

  for item in should_be_true:
    assert iterate._makeDidNothing( item ) is True

  for item in should_be_false:
    assert iterate._makeDidNothing( item ) is False

if __name__ == '__main__':
  print 'best when executed like: py.test -x %s' % __file__
  for i in dir():
    if i.startswith( 'test_' ):
      globals()[i]()
