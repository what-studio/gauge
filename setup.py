# -*- coding: utf-8 -*-
"""
"""
from __future__ import with_statement
import re
from setuptools import setup
from setuptools.command.test import test


# detect the current version
with open('gauge/__init__.py') as f:
    version = re.search(r'__version__\s*=\s*\'(.+?)\'', f.read()).group(1)
assert version


# use pytest instead
def run_tests(self):
    raise SystemExit(__import__('pytest').main(['-v']))
test.run_tests = run_tests


install_requires = ['six>=1.8.0', 'sortedcontainers>=0.8.2']
try:
    from weakref import WeakSet
except ImportError:
    # WeakSet was added in Python 2.7.
    install_requires.append('weakrefset>=1.0.0')
else:
    del WeakSet


setup(
    name='gauge',
    version=version,
    license='BSD',
    author='What! Studio',
    maintainer='Heungsub Lee',
    maintainer_email='sub@nexon.co.kr',
    url='https://github.com/what-studio/gauge',
    description='Deterministic linear gauge library',
    long_description=__doc__,
    platforms='any',
    packages=['gauge'],
    classifiers=['Development Status :: 4 - Beta',
                 'Intended Audience :: Developers',
                 'License :: OSI Approved :: BSD License',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'Programming Language :: Python :: 2',
                 'Programming Language :: Python :: 2.6',
                 'Programming Language :: Python :: 2.7',
                 'Programming Language :: Python :: 3',
                 'Programming Language :: Python :: 3.2',
                 'Programming Language :: Python :: 3.3',
                 'Programming Language :: Python :: 3.4',
                 'Programming Language :: Python :: Implementation :: CPython',
                 'Programming Language :: Python :: Implementation :: PyPy',
                 'Topic :: Games/Entertainment'],
    install_requires=install_requires,
    tests_require=['pytest'],
    test_suite='...',
)
