# Copyright (c) 2014, the Dart project authors.  Please see the AUTHORS file
# for details. All rights reserved. Use of this source code is governed by a
# BSD-style license that can be found in the LICENSE file.

vars = {
  "github_mirror":
      "https://chromium.googlesource.com/external/github.com/dart-lang/",
  "dart_root": "dart",
  "sdk_tag": "@1.19.0-dev.6.0",
  # yaml and all its dependencies are needed to run test.dart.
  "yaml_tag": "@2.1.10",
  "charcode_tag": "@1.1.0",
  "collection_tag": "@1.9.0",
  "path_tag": "@1.3.9",
  "source_span_tag": "@1.2.3",
  "string_scanner_tag": "@1.0.0",
}

deps = {
  Var("dart_root"):
      Var("github_mirror") + "sdk.git" + Var("sdk_tag"),
  Var("dart_root") + "/third_party/pkg/yaml":
      Var("github_mirror") + "yaml.git" + Var("yaml_tag"),
  Var("dart_root") + "/third_party/pkg/charcode":
      Var("github_mirror") + "charcode.git" + Var("charcode_tag"),
  Var("dart_root") + "/third_party/pkg/collection":
      Var("github_mirror") + "collection.git" + Var("collection_tag"),
  Var("dart_root") + "/third_party/pkg/path":
      Var("github_mirror") + "path.git" + Var("path_tag"),
  Var("dart_root") + "/third_party/pkg/source_span":
      Var("github_mirror") + "source_span.git" + Var("source_span_tag"),
  Var("dart_root") + "/third_party/pkg/string_scanner":
      Var("github_mirror") + "string_scanner.git" +
      Var("string_scanner_tag"),
}

hooks = [
  {
    'name': 'd8_testing_binaries',
    'pattern': '.',
    'action': [
      'download_from_google_storage',
      '--no_auth',
      '--no_resume',
      '--bucket',
      'dart-dependencies',
      '--recursive',
      '--directory',
      Var('dart_root') + '/third_party/d8',
    ],
  },
  {
    "name": "checked_in_dart_sdks",
    "pattern": ".",
    "action": [
      "download_from_google_storage",
      "--no_auth",
      "--no_resume",
      "--bucket",
      "dart-dependencies",
      "--recursive",
      "--auto_platform",
      "--extract",
      "--directory",
      Var('dart_root') + "/tools/sdks",
    ],
  },
  {
    "name": "gsutil",
    "pattern": ".",
    "action": [
      "download_from_google_storage",
      "--no_auth",
      "--no_resume",
      "--bucket",
      "dart-dependencies",
      "--extract",
      "-s",
      Var('dart_root') + "/third_party/gsutil.tar.gz.sha1",
    ],
  },
  {
    "name": "firefox_jsshell",
    "pattern": ".",
    "action": [
      "download_from_google_storage",
      "--no_auth",
      "--no_resume",
      "--bucket",
      "dart-dependencies",
      "--recursive",
      "--auto_platform",
      "--extract",
      "--directory",
      Var('dart_root') + "/third_party/firefox_jsshell",
    ],
  },
]
