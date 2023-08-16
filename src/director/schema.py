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

import sys
import strictyaml
from strictyaml import (EmptyNone,
                        Enum,
                        Int,
                        Map,
                        MapPattern,
                        Optional,
                        Regex,
                        Seq,
                        Str)

__DEFAULT_PRIORITY__ = 99

__SPEC_SCHEMA__ = Map({
    Optional("options") : Seq(MapPattern(Str(), EmptyNone() | Str())),
    "services" : MapPattern(Regex("^[a-zA-Z0-9._-]+$"), Map({
        Optional("priority", default=__DEFAULT_PRIORITY__) : Int(),
        Optional("name") : Regex("^[a-zA-Z0-9_][a-zA-Z0-9_-]*$"),
        Optional("makejail", default="Makejail") : Str(),
        Optional("options") : Seq(MapPattern(Str(), EmptyNone() | Str())),
        Optional("arguments") : Seq(MapPattern(Str(), Str())),
        Optional("environment") : Seq(MapPattern(Str(), EmptyNone() | Str())),
        Optional("volumes") : Seq(MapPattern(Str(), Str())),
        Optional("scripts") : Seq(Map({
            Optional("shell", default="/bin/sh -c") : Str(),
            Optional("type", default="jexec") : Enum(["jexec", "local", "chroot"]),
            "text" : Str()
        })),
        Optional("start") : Seq(MapPattern(Str(), Str())),
        Optional("serial", default=0) : Int()
    })),
    Optional("volumes") : MapPattern(Str(), Map({
        "device" : Str(),
        Optional("type", default="nullfs") : Str(),
        Optional("options", default="rw") : Str(),
        Optional("dump", default=0) : Int(),
        Optional("pass", default=0) : Int()
    }))
})

class Schema():
    def __init__(self, file):
        with open(file) as fd:
            self.spec = strictyaml.load(fd.read(), __SPEC_SCHEMA__)

    @property
    def options(self):
        return self.spec.data.get("options", [])

    @property
    def services(self):
        return self.spec.data.get("services")

    @property
    def volumes(self):
        return self.spec.data.get("volumes", {})
