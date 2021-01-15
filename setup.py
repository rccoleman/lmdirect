import setuptools

with open("README.md", "r") as f:
    readme = f.read()

setuptools.setup(
    name="lmdirect",
    version="0.7.0",
    description="A Python implementation of the local La Marzocco API",
    long_description=readme,
    long_description_content_type="text/markdown",
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
    packages=setuptools.find_packages(),
    install_requires=["pycryptodome>=3.9.9", "httpx>=0.16.1", "authlib>=0.15.2"],
    package_data={
        "license": ["LICENSE"],
    },
)
