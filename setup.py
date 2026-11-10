from setuptools import setup, find_packages

setup(
    name="geopulse",
    version="0.1.0",
    description="GeoPulse: Hyper-Local Retail Mobility Analytics",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.9",
)
