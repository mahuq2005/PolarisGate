from setuptools import setup, find_packages

with open("README.md") as f:
    long_description = f.read()

setup(
    name="polarisgate",
    version="1.0.0",
    description="Python SDK for the PolarisGate AI Content Safety Gateway",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="PolarisGate",
    packages=find_packages(),
    install_requires=["requests>=2.28"],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Security",
    ],
    extras_require={
        "dev": ["pytest>=7", "ruff>=0.1", "mypy>=1.0"],
    },
)