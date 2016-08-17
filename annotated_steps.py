#!/usr/bin/python

# Copyright (c) 2014, the Dart project authors.  Please see the AUTHORS file
# for details. All rights reserved. Use of this source code is governed by a
# BSD-style license that can be found in the LICENSE file.

import imp
import os
import re
import shutil
import shlex
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

# Some packages need all tests run sequentially, due to side effects.
# This list only affects tests run with 'pub run test'.
SERIALIZED_PACKAGES = [
  'analyzer_cli'
]

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

def GetSDK(bot_info):
  with BuildStep('Get sdk'):
    namer = bot_utils.GCSNamer(channel=bot_utils.Channel.DEV)
    # TODO(ricow): Be smarter here, only download if new.
    build_root = GetBuildRoot(bot_info)
    SafeDelete(os.path.join(build_root, 'dart-sdk'), bot_info)
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
      # We don't keep the execution bit if we use python's zipfile on posix.
      RunProcess(['unzip', local_zip, '-d', build_root])
    pub = GetPub(bot_info)
    RunProcess([pub, '--version'])

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

def SafeDelete(path, bot_info):
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
  SafeDelete(package_copy, bot_info)
  no_git = shutil.ignore_patterns('.git')
  shutil.copytree(package_path, copy_path, symlinks=False, ignore=no_git)
  return copy_path

def GetSdkBin(bot_info):
  return os.path.join(os.getcwd(), GetBuildRoot(bot_info),
                      'dart-sdk', 'bin')

def GetPub(bot_info):
  executable = 'pub.bat' if bot_info.system == 'windows' else 'pub'
  return os.path.join(GetSdkBin(bot_info), executable)

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
      args = [pub, 'upgrade', '--no-package-symlinks']
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
  'linux': ['d8', 'ff', 'chrome'],
  'mac': ['safari'],
}

is_first_test_run = True
def LogsArgument():
  global is_first_test_run
  if is_first_test_run:
    is_first_test_run = False
    return []
  return ['--append_logs']

def RunPackageTesting(bot_info, package_path, folder='test'):
  package_name = os.path.basename(package_path)
  if package_name == '':
    # when package_path had a trailing slash
    package_name = os.path.basename(os.path.dirname(package_path))
  if folder == 'build/test':
    suffix = ' under build'
    package_root = os.path.join(package_path, folder, 'packages')
    package_arg = '--package-root=%s' % package_root
  else:
    suffix = ''
    package_spec_file = os.path.join(package_path, '.packages')
    package_arg = '--packages=%s' % package_spec_file


  # Note: we use package_name/package_name/folder and not package_name/folder on
  # purpose. The first package_name denotes the suite, the second is part of the
  # path we want to match. Without the second package_name, we may match tests
  # that contain "folder" further down. So if folder is "test",
  # "package_name/test" matches "package_name/build/test", but
  # "package_name/package_name/test" does not.
  standard_args = ['--arch=ia32',
                   '--suite-dir=%s' % package_path,
                   '--use-sdk', '--report', '--progress=buildbot',
                   '--reset-browser-configuration',
                   package_arg,
                   '--write-debug-log', '-v',
                   '--time',
                   '%s/%s/%s/' % (package_name, package_name, folder)]
  with BuildStep('Test vm release mode%s' % suffix, swallow_error=True):
    args = [sys.executable, 'tools/test.py',
            '-mrelease', '-rvm', '-cnone'] + standard_args
    args.extend(LogsArgument())
    # For easy integration testing we give access to the sdk bin directory.
    # This only makes sense on vm testing.
    extra_env = { 'DART_SDK_BIN' : GetSdkBin(bot_info) }
    RunProcess(args, extra_env=extra_env)
  with BuildStep('Test analyzer%s' % suffix, swallow_error=True):
    args = [sys.executable, 'tools/test.py',
            '-mrelease', '-rnone', '-cdart2analyzer'] + standard_args
    args.extend(LogsArgument())
    RunProcess(args)
  # TODO(27065): Restore Dartium testing once it works on test.py again.
  for runtime in JS_RUNTIMES[bot_info.system]:
    with BuildStep('dart2js-%s%s' % (runtime, suffix), swallow_error=True):
      test_args = [sys.executable, 'tools/test.py',
                   '-mrelease', '-r%s' % runtime, '-cdart2js', '-j4',
                   '--dart2js-batch']
      args = test_args + standard_args
      args.extend(LogsArgument())
      _RunWithXvfb(bot_info, args)

def FillMagicMarkers(v, replacements):
  def replace(match):
    word = match.group(1)
    if not word in replacements:
      raise Exception("Unknown magic marker %s. Known mappings are: %s" %
                      (word, replacements))
    return replacements[word]
  return re.sub(r"\$(\w+)", replace, v)

def RunTestRunner(bot_info, test_package, package_path):
  package_name = os.path.basename(package_path)
  if package_name == '':
    # when package_path had a trailing slash
    package_name = os.path.basename(os.path.dirname(package_path))

  pub = GetPub(bot_info)
  extra_env = GetPubEnv(bot_info)
  with BuildStep('pub run test', swallow_error=True):
    # TODO(nweiz): include dartium here once sdk#23816 is fixed.
    platforms = set(['vm', 'chrome', 'firefox'])
    if bot_info.system == 'windows':
      platforms.add('ie')
      # TODO(nweiz): remove dartium here once sdk#23816 is fixed.
    elif bot_info.system == 'mac':
      platforms.add('safari')
      platforms.remove('firefox')

    if 'platforms' in test_package:
      platforms = platforms.intersection(set(test_package['platforms']))

    with utils.ChangedWorkingDirectory(package_path):
      test_args = [pub, 'run', 'test', '--reporter', 'expanded', '--no-color',
                   '--platform', ','.join(platforms)]
      if bot_info.package_name in SERIALIZED_PACKAGES:
          test_args.append('-j1')
      # TODO(6): If barback is needed, use --pub-serve option and pub serve test
      if test_package.get('barback'): test_args.append('build/test')
      _RunWithXvfb(bot_info, test_args, extra_env=extra_env)

def _RunWithXvfb(bot_info, args, **kwargs):
  if bot_info.system == 'linux':
    args = ['xvfb-run', '-a', '--server-args=-screen 0 1024x768x24'] + args
  RunProcess(args, **kwargs)

# Runs the script given by test_config.get_config if it exists, does nothing
# otherwise.
# Returns `True` if the script was run.
def RunCustomScript(test_config):
  custom_script = test_config.get_custom_script()
  if custom_script:
    command_string = FillMagicMarkers(custom_script, test_config.replacements)
    with BuildStep('Running custom script'):
      args = shlex.split(command_string, posix=False)
      print 'Running command: %s' % args
      sys.stdout.flush()
      exit_code = subprocess.call(args)
      if exit_code != 0:
        print "Custom script failed"
    return True
  else:
    return False

def RunDefaultScript(bot_info, test_config, copy_path):
  print "No custom script found, running default steps."

  GetSDK(bot_info)
  print 'Running testing in copy of package in %s' % copy_path
  RunPrePubUpgradeHooks(test_config)
  RunPubUpgrade(bot_info, copy_path)

  test_package = test_config.get_test_package()
  if test_package is None or test_package.get('barback'):
    RunPrePubBuildHooks(test_config)
    RunPubBuild(bot_info, copy_path, 'web')
    RunPubBuild(bot_info, copy_path, 'test', 'debug')
    RunPostPubBuildHooks(test_config)

  if test_package is not None:
    print 'Running the test package runner'
    RunPreTestHooks(test_config)
    RunTestRunner(bot_info, test_package, copy_path)
  else:
    print 'Running tests manually'
    FixupTestControllerJS(copy_path)
    RunPreTestHooks(test_config)
    RunPackageTesting(bot_info, copy_path, 'test')
    # TODO(6): Packages that need barback should use the test package runner,
    # instead of trying to run from the build/test directory.
    RunPackageTesting(bot_info, copy_path, 'build/test')

  RunPostTestHooks(test_config)


def RunHooks(hooks, section_name, replacements):
  for name, command in hooks.iteritems():
    command = FillMagicMarkers(command, replacements)
    with BuildStep('%s: %s' % (section_name, name), swallow_error=True):
      RunProcess(command, shell=True)

def RunPrePubUpgradeHooks(test_config):
  RunHooks(test_config.get_pre_pub_upgrade_hooks(), "Pre pub upgrade hooks",
           test_config.replacements)

def RunPrePubBuildHooks(test_config):
  RunHooks(test_config.get_pre_pub_build_hooks(), "Pre pub build hooks",
           test_config.replacements)

def RunPostPubBuildHooks(test_config):
  RunHooks(test_config.get_post_pub_build_hooks(), "Pre pub build hooks",
           test_config.replacements)

def RunPreTestHooks(test_config):
  RunHooks(test_config.get_pre_test_hooks(), "Pre test hooks",
           test_config.replacements)

def RunPostTestHooks(test_config):
  RunHooks(test_config.get_post_test_hooks(), "Post test hooks",
           test_config.replacements)

def main():
  bot_info = GetBotInfo()

  print 'Bot info: %s' % bot_info
  copy_path = GetPackageCopy(bot_info)
  config_file = os.path.join(copy_path, '.test_config')
  test_config = config_parser.ConfigParser(config_file)
  test_config.replacements = {
    'dart': utils.CheckedInSdkExecutable(),
    'project_root': copy_path,
    'python': sys.executable
  }

  RunCustomScript(test_config) or \
    RunDefaultScript(bot_info, test_config, copy_path)

if __name__ == '__main__':
  main()
