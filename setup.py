from setuptools import setup, find_packages

package_name = "nonlinear_avoidance"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Lukas Huber",
    maintainer_email="lukas.huber@epfl.ch",
    description="Nonlinear Rotational Obstacle Avoidance",
    license="TODO",
    # package_dir={'': 'src'},
    tests_require=["pytest"],
    # entry_points={
    # 'console_scripts': ['simulation_loader = pybullet_ros2.simulation_loader:main',
    # 'pybullet_ros2 = pybullet_ros2.pybullet_ros2:main']
    # }
)
