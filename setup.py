import os
from distutils.command.build import build

from django.core import management
from setuptools import setup, find_packages

try:
    with open(os.path.join(os.path.dirname(__file__), 'README.md'), encoding='utf-8') as f:
        long_description = f.read()
except:
    long_description = ''


class CustomBuild(build):
    def run(self):
        management.call_command('compilemessages', verbosity=1)
        build.run(self)


cmdclass = {
    'build': CustomBuild
}

setup(
    name='pretix-landing-pages',
    version='0.9.1',
    description='Custom landingpages for pretix organizers',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/DataManagementLab/pretix-landing-pages',
    author='BP 2019/20 Gruppe 45',
    author_email='benjamin.haettasch@cs.tu-darmstadt.de',

    license='Apache Software License',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Environment :: Web Environment',
        'Development Status :: 4 - Beta',
    ],

    install_requires=[],
    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    cmdclass=cmdclass,
    entry_points="""
[pretix.plugin]
pretix_landing_pages=pretix_landing_pages:PretixPluginMeta
""",
)
