# Copyright (c) 2014, the Dart project authors.  Please see the AUTHORS file
# for details. All rights reserved. Use of this source code is governed by a
# BSD-style license that can be found in the LICENSE file.

vars = {
  # We _don't_ inline this to allow the bots to use the mirror.
  "sdk_tag": "@1.12.0-dev.1.1",
  "googlecode_url": "http://%s.googlecode.com/svn",
  "gsutil_rev" : "@33376",
  "d8_rev" : "@39739",
  "firefox_jsshell_rev" : "@44282",
}

deps = {
  "dart":
       "https://chromium.googlesource.com/external/github.com" +
       "/dart-lang/sdk.git" + Var("sdk_tag"),
  "dart/third_party/d8":
      (Var("googlecode_url") % "dart") + "/third_party/d8" + Var("d8_rev"),
  "dart/third_party/gsutil":
      (Var("googlecode_url") % "dart") + "/third_party/gsutil" +
       Var("gsutil_rev"),
  "dart/third_party/firefox_jsshell":
      (Var("googlecode_url") % "dart") + "/third_party/firefox_jsshell" +
       Var("firefox_jsshell_rev"),
}

hooks = [
  {
    'name': 'checked_in_dart_binaries',
    'pattern': '.',
    'action': [
      'download_from_google_storage',
      '--no_auth',
      '--no_resume',
      '--bucket',
      'dart-dependencies',
      '-d',
      '-r',
      'dart/tools/testing/bin',
    ],
  },
]
