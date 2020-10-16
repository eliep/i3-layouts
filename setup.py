import setuptools

setuptools.setup(
    name='i3-layouts',
    version='0.5.0',
    description='More dynamics layouts for i3wm',
    url='http://github.com/eliep/i3-layouts',
    author='Elie',
    author_email='eprudhomme@gmail.com',
    license='MIT',
    packages=setuptools.find_packages(),
    install_requires=[
      'i3ipc'
    ],
    entry_points={
        'console_scripts': ['i3-layouts=i3l.cli:main']
    },
    zip_safe=False)
