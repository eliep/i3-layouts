import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='i3-layouts',
    version='0.9.3',
    description='Dynamics layouts for i3wm',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='http://github.com/eliep/i3-layouts',
    author='eliep',
    author_email='eprudhomme@gmail.com',
    license='MIT',
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
    install_requires=[
        'i3ipc'
    ],
    tests_require=[
        'python-xlib'
    ],
    entry_points={
        'console_scripts': ['i3-layouts=i3l.cli:main']
    },
    zip_safe=False)
