"""
Setup script for Windows Job Scheduler
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="windows-job-scheduler",
    version="1.0.0",
    author="Job Scheduler Team",
    author_email="contact@jobscheduler.com",
    description="A comprehensive Python-based job scheduling system for Windows environments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/windows-job-scheduler",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: System :: Systems Administration",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.800",
        ],
    },
    entry_points={
        "console_scripts": [
            "job-scheduler=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.yml", "*.json", "*.ps1", "*.html", "*.css", "*.js"],
        "web_ui": ["templates/*", "static/*"],
        "scripts": ["sample_scripts/*"],
        "config": ["*.yaml", "*.yml"],
    },
)