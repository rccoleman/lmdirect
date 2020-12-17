from setuptools import setup

with open('README.md', 'r') as f:
    readme = f.read()

setup(
    name='lmdirect',
    version='v0.1',
    description='A Python implementation of the local La Marzocco API',
    long_description=readme,
    url='https://github.com/rccoleman/lmdirect',
    author='Rob Coleman',
    author_email='rccoleman@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 1 - Experimental',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    packages=['lmdirect'],
    install_requires=[
        'pycryptodomex>=3.9.9; python_version > "3.8"'
    ],
    package_data={'license': ['LICENSE'],},
)
