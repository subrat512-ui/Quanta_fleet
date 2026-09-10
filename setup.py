from setuptools import find_packages, setup


setup(
    name="greenfleet",
    version="0.0.1",
    author="SIH Team",
    description="Green Fleet Management using Prediction and Optimization",
    # The importable packages live beneath ``src/``.  Explicitly declaring
    # this prevents setuptools from installing them as ``src.greenfleet``.
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[],
)
