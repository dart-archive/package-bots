package-bots
===================

This package contains a global configuration of Dart package bots, including the
annotated-steps used by our buildbot infrastructure and a small file that can be
used as a trigger for starting a new build in our bots (see `trigger.txt`).

## Using the `test` package runner

By default, the package bots will use [the SDK repository][sdk]'s custom test
runner to run the tests on the package bots. However, packages that use
[the new `test` package][test] can choose to use its runner instead. The
simplest way to do so is to set `test_package` to `true` in the `.test_config`
file:

```json
{
  "test_package": true
}
```

Note that when using the test runner, the `.status` file is ignored. Instead,
use [the test runner's `@TestOn` annotations][TestOn] to mark individual tests
that should pass or fail on particular platforms, or use the `"platforms"` key
to skip certain platforms entirely (see below).

[TestOn]: https://github.com/dart-lang/test#restricting-tests-to-certain-platforms

### Platform restrictions

By default, the package bots will run all browsers that are available on a given
platform, respecting the test package's `@TestOn` annotations. However, some
packages may not ever want to run on particular platforms; instead of specifying
a `@TestOn` annotation in every single file, these tests can specify a set of
allowed platforms in the configuration:

```json
{
  "test_package": {
    "platforms": ["vm", "dartium", "content-shell"]
  }
}
```

These platform names are the same names that are passed to the test runner. If
OS-specific platforms such as Internet Explorer are included, they will only be
run on the appropriate OS.

### Running with barback

Unlike the default behavior of the package bots, the `test` package runner
doesn't use barback by default. Packages can tell it to run their tests
transformed in the configuration:

```json
{
  "test_package": {
    "barback:" true
  }
}
```

This will cause the test runner to transform the `test` directory via `pub
build` and run `pub run test` against the result.

[sdk]: https://github.com/dart-lang/sdk
[test]: https://pub.dartlang.org/packages/test
