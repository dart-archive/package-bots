#!/usr/bin/python

# Copyright (c) 2014, the Dart project authors.  Please see the AUTHORS file
# for details. All rights reserved. Use of this source code is governed by a
# BSD-style license that can be found in the LICENSE file.

import imp
import os
import re
import shutil
import subprocess
import sys
import tempfile


# TODO(ricow): Remove this when we start downloading the sdk - we then don't
# need this.
DART_DIR = os.path.abspath(
    os.path.normpath(os.path.join(__file__, '..', '..', '..')))
utils = imp.load_source('utils', os.path.join(DART_DIR, 'tools', 'utils.py'))

# We are deliberately not using bot utils from the dart repo.

PACKAGES_BUILDER = r'packages-(windows|linux|mac)(-repo)?(-sample)?-(.*)'

class BotInfo(object):
  """
  Stores the info extracted from the bot name
  - system: windows, linux, mac
  - package-name
  """
  def __init__(self, system, package_name, is_repo, is_sample):
      self.system = system
      self.package_name = package_name
      self.is_repo = is_repo
      self.is_sample = is_sample

  def __str__(self):
    return "System: %s, Package-name: %s, Repo: %s, Sample: %s" % (
      self.system, self.package_name, self.is_repo, self.is_sample)

def GetBotInfo():
  name = os.environ.get('BUILDBOT_BUILDERNAME')
  if not name:
    print ("BUILDBOT_BUILDERNAME not defined. "
        "Expected pattern of the form: %s" % PACKAGES_BUILDER)
    exit(1)
  builder_pattern = re.match(PACKAGES_BUILDER, name)
  if builder_pattern:
    is_repo = builder_pattern.group(2) is not None
    is_sample = builder_pattern.group(3) is not None
    return BotInfo(builder_pattern.group(1),
                   builder_pattern.group(4),
                   is_repo,
                   is_sample)

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

class TempDir(object):
  def __init__(self, prefix=''):
    self._temp_dir = None
    self._prefix = prefix

  def __enter__(self):
    self._temp_dir = tempfile.mkdtemp(self._prefix)
    return self._temp_dir

  def __exit__(self, *_):
    shutil.rmtree(self._temp_dir, ignore_errors=True)

class ChangedWorkingDirectory(object):
  def __init__(self, working_directory):
    self._working_directory = working_directory

  def __enter__(self):
    self._old_cwd = os.getcwd()
    print "Enter directory = ", self._working_directory
    os.chdir(self._working_directory)

  def __exit__(self, *_):
    print "Enter directory = ", self._old_cwd
    os.chdir(self._old_cwd)

def RunProcess(command):
  """
  Runs command.

  If a non-zero exit code is returned, raises an OSError with errno as the exit
  code.
  """
  no_color_env = dict(os.environ)
  no_color_env['TERM'] = 'nocolor'
  print "Running: %s" % ' '.join(command)
  sys.stdout.flush()
  exit_code = subprocess.call(command, env=no_color_env)
  if exit_code != 0:
    raise OSError(exit_code)

def BuildSDK(bot_info):
  with BuildStep('Build sdk'):
    args = [sys.executable, 'tools/build.py',
            '-mrelease,debug',
            'create_sdk']
    RunProcess(args)

def GetPackagePath(bot_info):
  if bot_info.is_sample:
    if bot_info.is_repo:
      third_party = ['angular_tests', 'di_tests', 'html5lib']
      if bot_info.package_name in third_party:
        return os.path.join('samples', 'third_party', bot_info.package_name)
      return os.path.join('samples', bot_info.package_name)
    return os.path.join('third_party', 'samples', bot_info.package_name)
  if bot_info.is_repo:
    return os.path.join('pkg', bot_info.package_name)
  return os.path.join('third_party', 'pkg', bot_info.package_name)

def GetBuildRoot(bot_info):
  system = bot_info.system
  return utils.GetBuildRoot('win32' if system == 'windows' else system)

def GetPackageCopy(bot_info):
  build_root = GetBuildRoot(bot_info)
  package_copy = os.path.join(build_root, 'package_copy')
  package_path = GetPackagePath(bot_info)
  copy_path = os.path.join(package_copy, bot_info.package_name)
  # Clean out old copy
  shutil.rmtree(package_copy, ignore_errors=True)
  shutil.copytree(package_path, copy_path, symlinks=False)
  return copy_path

def GetPub():
  return os.path.join(os.getcwd(), 'out', 'ReleaseIA32',
                      'dart-sdk', 'bin', 'pub')

def RunPubUpgrade(path):
  pub = GetPub()
  with BuildStep('Pub upgrade'):
    # For now, assume pub
    with ChangedWorkingDirectory(path):
      args = [pub, 'upgrade']
      RunProcess(args)

def RunPubBuild(bot_info, path, mode=None):
  skip_pub_build = ['dart-protobuf']
  with BuildStep('Pub build'):
    if bot_info.package_name in skip_pub_build:
      print "Not running pub build"
      return
    pub = GetPub()
    with ChangedWorkingDirectory(path):
      if os.path.exists('test'):
        args = [pub, 'build']
        if mode:
            args.append('--mode=%s' % mode)
        args.append('test')
        RunProcess(args)

# Major hack
def FixupTestControllerJS(package_path):
  if os.path.exists(os.path.join(package_path, 'packages', 'unittest')):
    test_controller = os.path.join(package_path, 'packages', 'unittest',
                                   'test_controller.js')
    dart_controller = os.path.join('tools', 'testing', 'dart',
                                   'test_controller.js')
    print 'Hack test controller by copying of  %s to %s' % (dart_controller,
                                                            test_controller)
    shutil.copy(dart_controller, test_controller)
  else:
    print "No unittest to patch, do you even have tests"

JS_RUNTIMES = {
  'windows': ['d8', 'jsshell', 'ff', 'chrome', 'ie10'],
  'linux': ['d8', 'jsshell', 'ff', 'chrome'],
  'mac': ['d8', 'jsshell', 'safari', 'chrome'],
}

def RunPackageTesting(bot_info, package_path):
  package_root = os.path.join(package_path, 'packages')
  standard_args = ['--suite-dir=%s' % package_path,
                   '--use-sdk', '--report', '--progress=buildbot',
                   '--clear_browser_cache',
                   '--package-root=%s' % package_root]
  xvfb_args = ['xvfb-run', '-a', '--server-args=-screen 0 1024x768x24']
  system = bot_info.system
  with BuildStep('Test vm release mode', swallow_error=True):
    args = [sys.executable, 'tools/test.py',
            '-mrelease', '-rvm', '-cnone'] + standard_args
    RunProcess(args)
  with BuildStep('Test vm debug mode', swallow_error=True):
    args = [sys.executable, 'tools/test.py',
            '-mdebug', '-rvm', '-cnone'] + standard_args
    RunProcess(args)
  with BuildStep('Test dartium', swallow_error=True):
    test_args = [sys.executable, 'tools/test.py', 
                 '-mrelease', '-rdartium', '-cnone', '-j4']
    args = xvfb_args + test_args + standard_args
    RunProcess(args)

  # TODO(ricow/sigmund): add  drt
  needs_x = ['ff', 'drt', 'chrome']

  for runtime in JS_RUNTIMES[system]:
    with BuildStep('dart2js-%s' % runtime, swallow_error=True):
      xvfb = xvfb_args if runtime in needs_x and system == 'linux' else []
      test_args = [sys.executable, 'tools/test.py',
                   '-mrelease', '-r%s' % runtime, '-cdart2js', '-j4',
                   '--dart2js-batch']
      args = xvfb + test_args + standard_args
      RunProcess(args)

if __name__ == '__main__':
  bot_info = GetBotInfo()
  print 'Bot info: %s' % bot_info
  BuildSDK(bot_info)
  copy_path = GetPackageCopy(bot_info)
  print 'Running testing in copy of package in %s' % copy_path
  RunPubUpgrade(copy_path)
  RunPubBuild(bot_info, copy_path, 'debug')
  FixupTestControllerJS(copy_path)
  RunPackageTesting(bot_info, copy_path)
