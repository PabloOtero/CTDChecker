import codecs
import re
from setuptools import setup
from setuptools import find_packages

version = ''
with open('pyxylookup/__init__.py', 'r') as fd:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                        fd.read(), re.MULTILINE).group(1)

if not version:
    raise RuntimeError('Cannot find version information')

with codecs.open('README.rst', 'r', 'utf-8') as f:
    readme = f.read()

with codecs.open('Changelog.rst', 'r', 'utf-8') as f:
    changes = f.read()

long_description = readme + '\n\n' + changes

setup(
  name='pyxylookup',
  version=version,
  description='Python client for the OBIS xylookup API',
  long_description=long_description,
  author='Samuel Bosch',
  author_email='mail@samuelbosch.com',
  url='http://github.com/iobis/pyxylookup',
  license="MIT",
  packages=find_packages(exclude=['test-*']),
  install_requires=['requests>2.7',
                    'msgpack>=0.5.6',
                    'numpy>=1.14.0'],
  classifiers=(
    'Development Status :: 1 - Alpha',
    'Intended Audience :: Science/Research',
    'Topic :: Scientific/Engineering :: Bio-Informatics',
    'Natural Language :: English',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3'
  )
)
