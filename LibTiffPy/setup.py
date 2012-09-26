from distutils.core import setup

setup(
    name='LibTiffPy',
    version='0.1.0',
    author='Aron Vietti',
    author_email='aronvietti@gmail.com',
    packages=['libtiff', 'libtiff.test'],
    scripts=[],
    url='http://pypi.python.org/pypi/libtiff/',
    license='LICENSE.txt',
    description='Pure Python implementation of the libtiff API and library.',
    long_description=open('README.txt').read(),
    install_requires=[],
)