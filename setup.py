from setuptools import setup, find_packages

VERSION = "0.1.0"

def get_description():
    return "\
AppJail Director is a tool for running multi-jail environments on AppJail using a \
simple YAML specification. A Director file is used to define how one or more jails \
that make up your application are configured. Once you have a Director file, you \
can create and start your application with a single command: `appjail-director up`."

setup(
    name="director",
    version=VERSION,
    description="Define and run multi-jail environments with AppJail",
    long_description=get_description(),
    long_description_content_type="text/markdown",
    author="Jesús Daniel Colmenares Oviedo",
    author_email="DtxdF@disroot.org",
    url="https://github.com/DtxdF/director",
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Operating System :: POSIX :: BSD",
        "Operating System :: POSIX :: BSD :: FreeBSD",
        "Intended Audience :: System Administrators",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities"
    ],
    package_dir={"" : "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    license="BSD 3-Clause",
    license_files="LICENSE",
    install_requires=[
        "click",
        "strictyaml"
    ],
    entry_points={
        "console_scripts" : [
            "appjail-director = director.__init__:cli"
        ]
    }
)
