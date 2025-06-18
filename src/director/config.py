# BSD 3-Clause License
#
# Copyright (c) 2023, Jesús Daniel Colmenares Oviedo <DtxdF@disroot.org>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import configparser
import os
import sys

__DEFAULT_CONFIG__ = {
    "logs" : {
        "directory" : os.path.expanduser("~/.director/logs")
    },
    "projects" : {
        "directory" : os.path.expanduser("~/.director/projects")
    },
    "locks" : {
        "directory" : "/tmp/director/locks"
    },
    "jails" : {
        "remove_recursive" : False,
        "remove_force" : True
    },
    "commands" : {
        "timeout" : 1800
    }
}

__CONFIG__ = configparser.ConfigParser()

def load(file):
    __CONFIG__.read(file)

def get(*args, **kwargs):
    return _get(__CONFIG__.get, *args, **kwargs)

def getboolean(*args, **kwargs):
    return _get(__CONFIG__.getboolean, *args, **kwargs)

def getint(*args, **kwargs):
    return _get(__CONFIG__.getint, *args, **kwargs)

def _get(func, section, key, fallback=None):
    default = _get_default(section, key, fallback)

    return func(section, key, fallback=default)

def _get_default(section, key, fallback=None):
    _section = __DEFAULT_CONFIG__.get(section)

    if _section is not None:
        default = _section.get(key, fallback)
    else:
        default = fallback

    return default
