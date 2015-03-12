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
import zipfile

import config_parser

# We expect the tools directory from the dart repo to be checked out into:
# ../../tools
DART_DIR = os.path.abspath(
    os.path.normpath(os.path.join(__file__, '..', '..', '..')))
UTILS_PATH = os.path.join(DART_DIR, 'tools', 'utils.py')
BOT_UTILS_PATH = os.path.join(DART_DIR, 'tools', 'bots', 'bot_utils.py')
if os.path.isfile(UTILS_PATH):
  utils = imp.load_source('utils', UTILS_PATH)
else:
  print 'error: %s not found' % UTILS_PATH
  exit(1)
if os.path.isfile(BOT_UTILS_PATH):
  bot_utils = imp.load_source('bot_utils', BOT_UTILS_PATH)
else:
  print 'error: %s not found' % BOT_UTILS_PATH
  exit(1)


# We are deliberately not using bot utils from the dart repo.
PACKAGES_BUILDER = r'packages-(windows|linux|mac)(-repo)?(-sample)?-(.*)'

NAME_OVERRIDES = {
  'dart-protobuf' : 'protobuf',
  'polymer-dart' : 'polymer',
  'serialization.dart' : 'serialization',
  'unittest-stable' : 'unittest'
}

class BotInfo(object):
  """
  Stores the info extracted from the bot name
  - system: windows, linux, mac
  - package-name
  """
  def __init__(self, system, package_name, is_repo, is_sample):
      self.system = system
      self.package_name = NAME_OVERRIDES.get(package_name,
                                             package_name.replace('-', '_'))
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

def RunProcess(command, shell=False, extra_env=None):
  """
  Runs command.

  If a non-zero exit code is returned, raises an OSError with errno as the exit
  code.
  """
  env = dict(os.environ)
  env['TERM'] = 'nocolor'
  env['PUB_HOSTED_URL'] = 'https://buildbot-dart-dot-dartlang-pub.appspot.com'
  if 'GIT_USER_AGENT' in env:
    del env['GIT_USER_AGENT']
  if extra_env:
    env.update(extra_env)
  print "Running: %s" % ' '.join(command)
  print "env: %s" % str(env)
  sys.stdout.flush()
  exit_code = subprocess.call(command, env=env, shell=shell)
  if exit_code != 0:
    raise OSError(exit_code)

def BuildSDK(bot_info):
  with BuildStep('Build sdk'):
    args = [sys.executable, 'tools/build.py',
            '-mrelease,debug', '--arch=ia32',
            'create_sdk']
    RunProcess(args)

def GetSDK(bot_info):
  with BuildStep('Get sdk'):
    namer = bot_utils.GCSNamer(channel=bot_utils.Channel.DEV)
    # TODO(ricow): Be smarter here, only download if new.
    build_root = GetBuildRoot(bot_info)
    SafeDelete(os.path.join(build_root, 'dart-sdk'))
    if not os.path.exists(build_root):
      os.makedirs(build_root)
    local_zip = os.path.join(build_root, 'sdk.zip')
    gsutils = bot_utils.GSUtil()
    gsutils.execute(['cp',
                    namer.sdk_zipfilepath('latest', bot_info.system,
                                          'ia32', 'release'),
                    local_zip])
    if bot_info.system == 'windows':
      with zipfile.ZipFile(local_zip, 'r') as zip_file:
        zip_file.extractall(path=build_root)
    else:
      # We don't keep the execution bit if we use python's zipfile on possix.
      RunProcess(['unzip', local_zip, '-d', build_root])

def GetPackagePath(bot_info):
  if bot_info.is_repo:
    return os.path.join('pkg', bot_info.package_name)
  return os.path.join('third_party', 'pkg', bot_info.package_name)

def GetBuildRoot(bot_info):
  system = bot_info.system
  if system == 'windows':
    system = 'win32'
  if system == 'mac':
    system = 'macos'
  return utils.GetBuildRoot(system, mode='release', arch='ia32',
                            target_os=system)

def SafeDelete(path):
  if bot_info.system == 'windows':
    if os.path.exists(path):
      args = ['cmd.exe', '/c', 'rmdir', '/q', '/s', path]
      RunProcess(args)
  else:
    shutil.rmtree(path, ignore_errors=True)


def GetPackageCopy(bot_info):
  build_root = GetBuildRoot(bot_info)
  package_copy = os.path.join(build_root, 'package_copy')
  package_path = GetPackagePath(bot_info)
  copy_path = os.path.join(package_copy, bot_info.package_name)
  SafeDelete(package_copy)
  no_git = shutil.ignore_patterns('.git')
  shutil.copytree(package_path, copy_path, symlinks=False, ignore=no_git)
  return copy_path

def GetSdkBin():
  return os.path.join(os.getcwd(), GetBuildRoot(bot_info),
                      'dart-sdk', 'bin')

def GetVM():
  executable = 'dart.exe' if bot_info.system == 'windows' else 'dart'
  return os.path.join(GetSdkBin(), executable)

def GetPub(bot_info):
  executable = 'pub.bat' if bot_info.system == 'windows' else 'pub'
  return os.path.join(GetSdkBin(), executable)

def GetPubEnv(bot_info):
  return {'PUB_CACHE' : os.path.join(os.getcwd(),
      GetBuildRoot(bot_info), 'pub_cache') }

# _RunPubCacheRepair and _CheckPubCacheCorruption are not used right now, but we
# keep them around because they provide an easy way to diagnose and fix issues
# in the bots.
def _RunPubCacheRepair(bot_info, path):
  pub = GetPub(bot_info)
  extra_env = GetPubEnv(bot_info)
  with BuildStep('Pub cache repair'):
    # For now, assume pub
    with ChangedWorkingDirectory(path):
      args = [pub, 'cache', 'repair']
      RunProcess(args, extra_env=extra_env)

corruption_checks = 0
def _CheckPubCacheCorruption(bot_info, path):
  extra_env = GetPubEnv(bot_info)
  global corruption_checks
  corruption_checks += 1
  with BuildStep('Check pub cache corruption %d' % corruption_checks):
    with ChangedWorkingDirectory(path):
      packages = os.path.join(
        extra_env['PUB_CACHE'], 'hosted', 'pub.dartlang.org')
      print '\nLooking for packages in %s:' % str(packages)
      if not os.path.exists(packages):
        print "cache directory doesn't exist"
        return
      for package in os.listdir(packages):
        if 'unittest-' in package:
          exists = os.path.exists(
                  os.path.join(packages, package, 'lib', 'unittest.dart'))
          print '- ok:  ' if exists else '- bad: ',
          print os.path.join(package, 'lib', 'unittest.dart')
      print ''

def RunPubUpgrade(bot_info, path):
  pub = GetPub(bot_info)
  extra_env = GetPubEnv(bot_info)
  with BuildStep('Pub upgrade'):
    # For now, assume pub
    with ChangedWorkingDirectory(path):
      args = [pub, 'upgrade']
      RunProcess(args, extra_env=extra_env)

def RunPubBuild(bot_info, path, folder, mode=None):
  skip_pub_build = ['dart-protobuf', 'rpc']
  with BuildStep('Pub build on %s' % folder):
    if bot_info.package_name in skip_pub_build:
      print "Not running pub build"
      return
    pub = GetPub(bot_info)
    extra_env = GetPubEnv(bot_info)
    with ChangedWorkingDirectory(path):
      # run pub-build on the web folder
      if os.path.exists(folder):
        args = [pub, 'build']
        if mode:
            args.append('--mode=%s' % mode)
        if folder != 'web':
            args.append(folder)
        RunProcess(args, extra_env=extra_env)

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
  'windows': ['ff', 'chrome', 'ie10'],
  'linux': ['d8', 'jsshell', 'ff', 'chrome'],
  'mac': ['safari'],
}

def RunPackageTesting(bot_info, package_path):
  package_root = os.path.join(package_path, 'packages')
  standard_args = ['--suite-dir=%s' % package_path,
                   '--use-sdk', '--report', '--progress=buildbot',
                   '--clear_browser_cache',
                   '--package-root=%s' % package_root,
                   '--write-debug-log', '-v',
                   '--time']
  system = bot_info.system
  xvfb_command = ['xvfb-run', '-a', '--server-args=-screen 0 1024x768x24']
  xvfb_args =  xvfb_command if system == 'linux' else []
  with BuildStep('Test vm release mode', swallow_error=True):
    args = [sys.executable, 'tools/test.py',
            '-mrelease', '-rvm', '-cnone'] + standard_args
    RunProcess(args)
  with BuildStep('Test analyzer', swallow_error=True):
    args = [sys.executable, 'tools/test.py',
            '-mrelease', '-rnone', '-cdart2analyzer'] + standard_args
    RunProcess(args)
  if bot_info.system != 'windows':
    with BuildStep('Test dartium', swallow_error=True):
      test_args = [sys.executable, 'tools/test.py',
                   '-mrelease', '-rdartium', '-cnone', '-j4']
      args = xvfb_args + test_args + standard_args
      RunProcess(args)

  for runtime in JS_RUNTIMES[system]:
    with BuildStep('dart2js-%s' % runtime, swallow_error=True):
      test_args = [sys.executable, 'tools/test.py',
                   '-mrelease', '-r%s' % runtime, '-cdart2js', '-j4',
                   '--dart2js-batch']
      args = xvfb_args + test_args + standard_args
      RunProcess(args)


def RunHooks(hooks, section_name):
  for name, command in hooks.iteritems():
    with BuildStep('%s: %s' % (section_name, name), swallow_error=True):
      RunProcess(command, shell=True)

def RunPrePubUpgradeHooks(test_config):
  RunHooks(test_config.get_pre_pub_upgrade_hooks(), "Pre pub upgrade hooks")

def RunPrePubBuildHooks(test_config):
  RunHooks(test_config.get_pre_pub_build_hooks(), "Pre pub build hooks")

def RunPreTestHooks(test_config):
  RunHooks(test_config.get_pre_test_hooks(), "Pre test hooks")

def RunPostTestHooks(test_config):
  RunHooks(test_config.get_post_test_hooks(), "Post test hooks")

if __name__ == '__main__':
  bot_info = GetBotInfo()
  print 'Bot info: %s' % bot_info
  copy_path = GetPackageCopy(bot_info)
  config_file = os.path.join(copy_path, '.test_config')
  test_config = config_parser.ConfigParser(config_file,
                                           GetVM(),
                                           copy_path)
  GetSDK(bot_info)
  print 'Running testing in copy of package in %s' % copy_path
  RunPrePubUpgradeHooks(test_config)
  RunPubUpgrade(bot_info, copy_path)

  RunPrePubBuildHooks(test_config)
  RunPubBuild(bot_info, copy_path, 'web')
  RunPubBuild(bot_info, copy_path, 'test', 'debug')
  FixupTestControllerJS(copy_path)

  RunPreTestHooks(test_config)
  RunPackageTesting(bot_info, copy_path)
  RunPostTestHooks(test_config)
