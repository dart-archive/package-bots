#!/usr/bin/python

# Copyright (c) 2014, the Dart project authors.  Please see the AUTHORS file
# for details. All rights reserved. Use of this source code is governed by a
# BSD-style license that can be found in the LICENSE file.

import os
import re
import subprocess
import sys

# We are deliberately not using bot utils from the dart repo.

PACKAGES_BUILDER = r'packages-(windows|linux|mac)-(.*)'

class BotInfo(object):
  """
  Stores the info extracted from the bot name
  - system: windows, linux, mac
  - package-name
  """
  def __init__(self, system, package_name):
      self.system = system
      self.package_name = package_name

  def __str__(self):
    return "System: %s, Package-name: %s" % (self.system, self.package_name)

def GetBotInfo():
  name = os.environ.get('BUILDBOT_BUILDERNAME')
  builder_pattern = re.match(PACKAGES_BUILDER, name)
  if builder_pattern:
    return BotInfo(builder_pattern.group(1),
                   builder_pattern.group(2))

class BuildStep(object):
  """
  A context manager for handling build steps.

  When the context manager is entered, it prints the "@@@BUILD_STEP __@@@"
  message. If it exits from an error being raised it displays the
  "@@@STEP_FAILURE@@@" message.

  If swallow_error is True, then this will catch and discard any OSError that
  is thrown. This lets you run later BuildSteps if the current one fails.
  """
  def __init__(self, name, swallow_error=False):
    self.name = name
    self.swallow_error = swallow_error

  def __enter__(self):
    print '@@@BUILD_STEP %s@@@' % self.name
    sys.stdout.flush()

  def __exit__(self, type, value, traceback):
    if value:
      print '@@@STEP_FAILURE@@@'
      sys.stdout.flush()
      if self.swallow_error and isinstance(value, OSError):
        return True

def RunProcess(command):
  """
  Runs command.

  If a non-zero exit code is returned, raises an OSError with errno as the exit
  code.
  """
  no_color_env = dict(os.environ)
  no_color_env['TERM'] = 'nocolor'

  exit_code = subprocess.call(command, env=no_color_env)
  if exit_code != 0:
    raise OSError(exit_code)

def BuildSDK(bot_info):
  with BuildStep('Build sdk'):
    args = [sys.executable, 'tools/build.py',
            '-mrelease',
            'create_sdk']
    RunProcess(args)

def RunPackageTesting(bot_info):
  with BuildStep('Test vm release mode', swallow_error=True):
    args = [sys.executable, 'tools/test.py',
            '--suite-dir=third_party/pkg/%s' % bot_info.package_name,
            '-mrelease', '-rvm', '-cnone']
    RunProcess(args)
  with BuildStep('Test vm debug mode', swallow_error=True):
    args = [sys.executable, 'tools/test.py',
            '--suite-dir=third_party/pkg/%s' % bot_info.package_name,
            '-mrelease', '-rvm', '-cnone']
    RunProcess(args)

  with BuildStep('Test dartium', swallow_error=True):
    args = [sys.executable, 'tools/test.py',
            '--suite-dir=third_party/pkg/%s' % bot_info.package_name,
            '-mrelease', '-rdartium', '-cnone']
    RunProcess(args)


  # TODO(ricow): add mac/windows and generalize to top level list
  runtimes = ['d8', 'jsshell', 'ff', 'drt']

  for runtime in runtimes:
    with BuildStep('dart2js-%s' % runtime, swallow_error=True):
      args = [sys.executable, 'tools/test.py',
              '--suite-dir=third_party/pkg/%s' % bot_info.package_name,
              '-mrelease', '-r%s' % runtime, '-cdart2js', '-j1']
      RunProcess(args)


if __name__ == '__main__':
  bot_info = GetBotInfo()
  print 'Bot info: %s' % bot_info
  BuildSDK(bot_info)
  RunPackageTesting(bot_info)
