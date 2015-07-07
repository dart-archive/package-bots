#!/usr/bin/python
# Copyright (c) 2014, the Dart project authors.  Please see the AUTHORS file
# for details. All rights reserved. Use of this source code is governed by a
# BSD-style license that can be found in the LICENSE file.

import os
import json

def _TestDictOfStrings(key, value):
  if not isinstance(value, dict):
    raise Exception('Wrong type for key "%s", expecting dict, got %s.' %
                    (key, type(value)))
  for k, v in value.iteritems():
    if not isinstance(k, basestring):
      raise Exception("In %s the decription %s was not a string but %s" %
                      (key, k, type(k)))
    if not isinstance(v, basestring):
      raise Exception("In %s the command %s was not a string but %s" %
                      (key, v, type(v)))

def _TestListOfStrings(key, value):
  if not isinstance(value, list):
    raise Exception('Wrong type for key "%s", expecting list, got %s.' %
                    (key, type(value)))

  for element in value:
    if not isinstance(element, basestring):
      raise Exception("In %s, %s was not a string but %s" %
                      (key, k, type(k)))

def _TestString(key, value):
  if not isinstance(value, basestring):
    raise Exception('Wrong type for key "%s", expecting string, got %s.' %
                    (key, type(value)))

def _TestBoolean(key, value):
  if not isinstance(value, bool):
    raise Exception('Wrong type for key "%s", expecting boolean, got %s.' %
                    (key, type(value)))

def _TestPackageConfig(key, value):
  if isinstance(value, bool): return True
  if not isinstance(value, dict):
    raise Exception('Wrong type for key "%s", expecting bool or dict, got %s.' %
                    (key, type(value)))

  keys = value.keys()

  if 'platforms' in keys:
    _TestListOfStrings('%s.platforms' % key, value['platforms'])
    keys.remove('platforms')

  if 'barback' in keys:
    _TestBoolean('%s.barback' % key, value['barback'])
    keys.remove('barback')

  if keys:
    raise Exception('In %s, unexpected key %s' %
                    (key, keys[0]))

VALID_TYPES = {
  # Hooks mapping names (as displayed by the buildbot) to commands to execute.
  'pre_pub_upgrade_hooks' : _TestDictOfStrings,
  'pre_pub_build_hooks' : _TestDictOfStrings,
  'post_pub_build_hooks' : _TestDictOfStrings,
  'pre_test_hooks' : _TestDictOfStrings,
  'post_test_hooks' : _TestDictOfStrings,
  # Using a custom script to run steps.
  'use_custom_script' : _TestString,
  # Using or configuring the test package
  'test_package' : _TestPackageConfig,
}

"""
Example config:
{
  "pre_pub_build_hooks" : {
      "Fixing up something": "$dart $project_root/test.dart first"
  },
  "post_pub_build_hooks" : {
      "Fixing up something": "$dart $project_root/test.dart first"
  },
  "pre_pub_upgrade_hooks" : {
      "Mess up": "$dart $project_root -la"
  },
  "pre_test_hooks" : {
      "Fix tests": "$dart $project_root/test.dart foo",
      "Fix tests some more": "$dart $project_root/test.dart bar"
  },
  "post_test_hooks" : {
      "Code coverage": "$dart $project_root/test.dart coverage"
  }
}

Alternatively you can give a custom script to run:
{
  "use_custom_script" : "$python tools/annotated_scripts.py"
}
"""


class ConfigParser(object):
  """
  Encapsulation of package testing config.
  Hooks, which are lists of commands, are read from a JSON file.
  The objects are simply instantiated with a file parameter.
  - file: The file to get the config from
  There are a number of magic markers that can be used in the config:
    $dart: the full path to the Dart vm
    $project_root: path to the package being tested
    $python: path to a python executable
  """
  def __init__(self, file):
    self.config = self._get_config(file)
    self._validate_config_file()

  def _validate_config_file(self):
    for (key, value) in self.config.iteritems():
      if not (key in VALID_TYPES):
        raise Exception("Unknown configuration key %s" % key)
      type_test = VALID_TYPES[key]
      type_test(key, value)
    if "use_custom_script" in self.config and len(self.config) > 1:
      raise Exception("Cannot use 'use_custom_script' combined with hooks.")

  def _get_hooks(self, hook_kind):
    return self.config.get(hook_kind) or {}

  def get_pre_pub_upgrade_hooks(self):
    return self._get_hooks('pre_pub_upgrade_hooks')

  def get_pre_pub_build_hooks(self):
    return self._get_hooks('pre_pub_build_hooks')

  def get_post_pub_build_hooks(self):
    return self._get_hooks('post_pub_build_hooks')

  def get_pre_test_hooks(self):
    return self._get_hooks('pre_test_hooks')

  def get_post_test_hooks(self):
    return self._get_hooks('post_test_hooks')

  def get_custom_script(self):
    return self.config.get('use_custom_script') or None

  # TODO(nweiz): Use the test package by default once all packages use it. Use
  # its configuration file once that exists (test#46) rather than doing
  # bot-specific configuration.
  def get_test_package(self):
    value = self.config.get('test_package')
    print("test package config: %s" % value)
    if isinstance(value, bool): return {} if value else None
    return value

  def _get_config(self, file):
    if os.path.isfile(file):
      return json.loads(open(file).read())
    else:
      print("No config test file in package")
      return {}

  def __str__(self):
    config_string = json.dumps(self.config, indent=2)
    return 'dart: %s\nproject_root: %s\nconfig: \n%s' % (self.dart_binary,
                                                         self.project_root,
                                                         config_string)

if __name__ == '__main__':
  parser = ConfigParser('.test_config', 'daaaaaart', 'foobar')
  parser.get_pre_pub_build_hooks()
  parser.get_pre_pub_upgrade_hooks()
  parser.get_pre_test_hooks()
  parser.get_post_test_hooks()
  print parser


