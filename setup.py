
"""Setup configuration for JOJI Oi system."""

from setuptools import setup, find_packages
import os

# Read README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Read requirements
def read_requirements(filename):
    with open(filename, "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="jojiai",
    version="1.0.0",
    author="JOJI Oi Development Team",
    author_email="dev@jojiai.com",
    description="AI-powered memory system with race condition fixes and comprehensive monitoring",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/gtsurkav-sudo/JOJIAI",
    project_urls={
        "Bug Tracker": "https://github.com/gtsurkav-sudo/JOJIAI/issues",
        "Documentation": "https://github.com/gtsurkav-sudo/JOJIAI/wiki",
        "Source Code": "https://github.com/gtsurkav-sudo/JOJIAI",
    },
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.9",
    install_requires=[
        "prometheus-client>=0.17.0",
        "python-json-logger>=2.0.0",
        "click>=8.0.0",
    ],
    extras_require={
        "dev": [
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "bandit>=1.7.0",
            "safety>=2.3.0",
        ],
        "test": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-xdist>=3.0.0",
            "pytest-mock>=3.10.0",
            "pytest-timeout>=2.1.0",
            "pytest-benchmark>=4.0.0",
            "memory-profiler>=0.60.0",
            "psutil>=5.9.0",
        ],
        "monitoring": [
            "grafana-client>=3.5.0",
            "alertmanager-client>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "memoryctl=jojiai.memoryctl:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "jojiai": ["*.json", "*.yaml", "*.yml"],
    },
    zip_safe=False,
)
