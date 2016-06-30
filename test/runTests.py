#!/usr/bin/env python
from __future__                import print_function, division, unicode_literals, absolute_import
from test_tools.helpers        import *
from test_tools.runChanged     import *
from test_tools.runPackage     import run_package
from test_tools.readyaml       import read_yaml
from test_tools.genPackageInfo import gen_package_info
import sys

config = read_yaml('test_tools/testconfig.yml')

slowTests = config['slow-tests']
    
if __name__ == "__main__":
    # Setup arguments and other variables:
    args, kwargs = get_args(sys.argv)
    exclude = ['benchmarks', 'output', 'cmp_chk_files', 'temp_test_files', 'test_tools']

    # Specify the versions of your test :)
    if 'version' not in kwargs:
        pythonCommands = ['python%s.%s' % (sys.version_info[0], sys.version_info[1])]
    else:
        pythonCommands = ['python%s' % kwargs['version']]
    
    if 'fast-only' in kwargs:
        exclude += slowTests # Shave off ~3 hrs?

    # Since last commit to current branch
    if len(args[0]) == 0:
        if 'changed' in kwargs:
            packageNames = [name for name in get_changed_test_packages() if name not in exclude]
        else:
            packageNames = [name for name in get_package_names() if name not in exclude]
    else:
        packageNames = args[0]

    print('Running packages %s' % (', '.join(packageNames)))

    # Generating info
    if 'info' in kwargs:
        gen_package_info(packageNames)

    # Only running tests
    else:
        if 'nose' in kwargs:
            pythonCommands += ['-m', 'nose']

        lastFailed = 'True' if 'lastFailed' in kwargs else None
        for package in packageNames:
            run_package(package, precommands=pythonCommands, postcommand=None, lastFailed=lastFailed)

