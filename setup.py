# -*- coding: utf-8 -*-
"""
"""
from __future__ import with_statement
import re
from setuptools import setup
from setuptools.command.test import test


# detect the current version
with open('gauge.py') as f:
    version = re.search(r'__version__\s*=\s*\'(.+?)\'', f.read()).group(1)
assert version


# use pytest instead
def run_tests(self):
    pyc = re.compile(r'\.pyc|\$py\.class')
    test_file = pyc.sub('.py', __import__(self.test_suite).__file__)
    raise SystemExit(__import__('pytest').main(['-xv', test_file]))
test.run_tests = run_tests


setup(
    name='gauge',
    version=version,
    license='BSD',
    author='Heungsub Lee',
    author_email=re.sub('((sub).)(.*)', r'\2@\1.\3', 'sublee'),
    url='https://github.com/sublee/gauge',
    description='Deterministic linear gauge library',
    long_description=__doc__,
    platforms='any',
    py_modules=['gauge'],
    classifiers=['Development Status :: 4 - Beta',
                 'Intended Audience :: Developers',
                 'License :: OSI Approved :: BSD License',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'Programming Language :: Python :: Implementation :: CPython',
                 'Programming Language :: Python :: Implementation :: PyPy',
                 'Topic :: Games/Entertainment'],
    install_requires=['sortedcontainers>=0.8.2'],
    tests_require=['pytest'],
    test_suite='gaugetest',
)
