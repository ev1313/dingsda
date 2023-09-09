#!/usr/bin/env python
from setuptools import setup
from dingsda.version import version_string

setup(
    name = "dingsda",
    version = version_string,
    packages = [
        'dingsda',
        'dingsda.lib',
    ],
    license = "MIT",
    description = "A powerful declarative symmetric parser/builder for binary data with XML de- and encoding",
    long_description = open("README.rst").read(),
    platforms = ["POSIX", "Windows"],
    url = "http://dingsda.readthedocs.org",
    project_urls = {
        "Source": "https://github.com/ev1313/dingsda",
        "Documentation": "https://dingsda.readthedocs.io/en/latest/",
        "Issues": "https://github.com/ev1313/dingsda/issues",
    },
    author = "Tim Blume",
    author_email = "dingsda@3nd.io",
    python_requires = ">=3.10",
    install_requires = [],
    extras_require = {
        "extras": [
            "enum34",
            "numpy",
            "arrow",
            "ruamel.yaml",
            "lz4",
            "cryptography"
        ],
    },
    keywords = [
        "dingsda",
        "construct",
        "declarative",
        "data structure",
        "struct",
        "binary",
        "symmetric",
        "parser",
        "builder",
        "parsing",
        "building",
        "pack",
        "unpack",
        "packer",
        "unpacker",
        "xml"
    ],
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Build Tools",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
)
