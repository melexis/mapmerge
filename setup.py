from setuptools import setup, find_packages

setup(
    name='mapmerge',
    description='electronic wafermap processor for mapmerge',
    version='1.0.1',
    long_description=__doc__,
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests", '*send_job.py', '*stomptest.py']),
    zip_safe=False,
    install_requires=[],
    scripts=['python-mapmerge']
)
