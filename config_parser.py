#!/usr/bin/python
# Copyright (c) 2014, the Dart project authors.  Please see the AUTHORS file
# for details. All rights reserved. Use of this source code is governed by a
# BSD-style license that can be found in the LICENSE file.

import os
import json

VALID_TYPES = {
  # Hooks mapping names (as displayed by the buildbot) to commands to execute.
  'pre_pub_upgrade_hooks' : dict,
  'pre_pub_build_hooks' : dict,
  'pre_test_hooks' : dict,
  'post_test_hooks' : dict
}

"""
Example config:
{
  "pre_pub_build_hooks" : {
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
  """
  def __init__(self, file, dart_binary, project_root):
    self.config = self._get_config(file)
    self.dart_binary = dart_binary
    self.project_root = project_root

  def _validate_config_value(self, value, key):
    valid_types = VALID_TYPES[key]
    if value:
      if isinstance(value, valid_types):
        return value
      else:
        error = 'Wrong type for key "%s", expecting %s, got %s' % (key,
                                                                   valid_types,
                                                                   type(value))
        raise Exception(error)

  def _is_string(self, value):
    return isinstance(value, basestring)

  def _guarantee_dict_of_strings(self, hooks):
    if len(hooks) == 0:
      return
    if not all([self._is_string(v) for v in hooks.keys()]):
      raise Exception("Command names must be strings, was %s" % hooks)
    if not all([self._is_string(v) for v in hooks.values()]):
      raise Exception("All commands must be strings, was %s" % hooks)

  def _fill_magic_markers(self, hooks):
    for k, v in hooks.iteritems():
      v = v.replace('$dart', self.dart_binary)
      v = v.replace('$project_root', self.project_root)
      hooks[k] = v

  def _get_hooks(self, hook_kind):
    hooks = self._validate_config_value(self.config.get(hook_kind),
                                        hook_kind) or {}
    self._guarantee_dict_of_strings(hooks)
    self._fill_magic_markers(hooks)
    return hooks

  def get_pre_pub_upgrade_hooks(self):
    return self._get_hooks('pre_pub_upgrade_hooks')

  def get_pre_pub_build_hooks(self):
    return self._get_hooks('pre_pub_build_hooks')

  def get_pre_test_hooks(self):
    return self._get_hooks('pre_test_hooks')

  def get_post_test_hooks(self):
    return self._get_hooks('post_test_hooks')

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


