#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="nemesis-cli",
    version="5.0.0",
    description="Agent de codage IA ultra-moderne inspire de Claude Code",
    author="Nemesis Team",
    packages=find_packages(where="."),
    package_dir={"": "."},
    py_modules=["nemesis"],
    include_package_data=True,
    package_data={
        "prompts": ["*.txt"],
    },
    entry_points={
        "console_scripts": [
            "nemesis=nemesis:main",
        ],
    },
    install_requires=[
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
    ],
    python_requires=">=3.8",
)
