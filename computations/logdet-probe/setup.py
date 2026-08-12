from setuptools import setup, find_packages

setup(
    name="logdet_probe",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "numpy>=1.20.0",
    ],
    extras_require={
        "torch": ["torch>=2.0.0"],
    },
    description="Canonical cross-package logdet covariance probe (S_horizon / conditioning / capacity) for Moe and NOX",
    python_requires=">=3.10",
    author="second-brain unification (TASK 3)",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
    ],
)
