from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="lmdirect",
    version="v0.3",
    description="A Python implementation of the local La Marzocco API",
    long_description=readme,
    url="https://github.com/rccoleman/lmdirect",
    author="Rob Coleman",
    author_email="rccoleman@gmail.com",
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
    python_requires='>=3.8',
    packages=["lmdirect"],
    install_requires=["pycryptodome>=3.9.9"],
    package_data={
        "license": ["LICENSE"],
    },
)
