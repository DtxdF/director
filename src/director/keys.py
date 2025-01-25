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

import os
import shutil

class Key():
    def __init__(self, directory):
        self.directory = directory

    def set_key(self, key, value):
        keyfile = self.get_keyfile(key)

        dirname = os.path.dirname(keyfile)

        if dirname != "":
            os.makedirs(dirname, exist_ok=True)

        with open(keyfile, "wb", buffering=0) as fd:
            fd.write(value.encode())

    def get_key(self, key, default=None):
        if not self.has_key(key):
            return default

        keyfile = self.get_keyfile(key)

        with open(keyfile, "r") as fd:
            return fd.read()

    def has_key(self, key):
        return os.path.isfile(self.get_keyfile(key))

    def unset_key(self, key):
        keyfile = self.get_keyfile(key)

        if os.path.isfile(keyfile):
            os.remove(keyfile)
        else:
            shutil.rmtree(keyfile, ignore_errors=True)

    def get_keyfile(self, key):
        return os.path.join(self.directory, key)
