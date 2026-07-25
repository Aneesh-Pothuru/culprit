"""Compatibility metadata for older offline setuptools environments."""

from setuptools import find_packages, setup


setup(
    name="culprit-debugger",
    version="0.2.0",
    description="Execution-backed attribution for multi-model stacks",
    packages=find_packages("src"),
    package_dir={"": "src"},
    package_data={"culprit": ["resources/*.json"]},
    python_requires=">=3.10",
    entry_points={"console_scripts": ["culprit=culprit.cli:main"]},
    extras_require={"mcap": ["mcap>=1.2", "mcap-ros2-support>=0.5"]},
)
