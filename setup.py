# pylint: skip-file
from setuptools import find_packages, setup

package_name = "bencher"

setup(
    name=package_name,
    description="A library for benchmarking code and generating reports for analysis",
    # maintainer="austin.gregg-smith",
    # maintainer_email="austin.gregg-smith@dyson.com",
    packages=find_packages(exclude=["test.*", "test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    zip_safe=False,
    test_suite="test",
    tests_require=["pytest"],
)
