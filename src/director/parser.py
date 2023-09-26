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

import re

import pyaml_env

import director.exceptions

def load(file):
    document = pyaml_env.parse_config(file, default_value="")

    validate(document)

    return document

def validate(document):
    if not isinstance(document, dict):
        raise director.exceptions.InvalidSpec("Invalid document specification.")

    options = document.get("options")

    if options is not None:
        __check_options(options)

    services = document.get("services")

    if services is None:
        raise director.exceptions.InvalidSpec("services: Required but not defined.")
    else:
        __check_services(services)

    volumes = document.get("volumes")

    if volumes is not None:
        __check_volumes(volumes)

def __check_options(options):
    __check_generic_list(options, "options")

def __check_services(services):
    if not isinstance(services, dict):
        raise director.exceptions.InvalidSpec("services: Must be a Mapping.")

    for nro, name in enumerate(services, 1):
        if not isinstance(name, str):
            name = str(name)

        if not re.match(r"^[a-zA-Z0-9._-]+$", name):
            raise director.exceptions.InvalidSpec(f"services ({name} / #{nro}): Service name is incorrect.")

        service = services[name]

        if not isinstance(service, dict):
            raise director.exceptions.InvalidSpec(f"services/{name} (#{nro}): Must be a Mapping.")

        __check_service(service, name, nro)

def __check_service(service, name, nro):
    _id = f"services/{name}"
    
    priority = service.get("priority")

    if priority is not None and not isinstance(priority, int):
        raise director.exceptions.InvalidSpec(f"{_id} (priority / #{nro}): Must be an Integer.")

    jail_name = service.get("name")

    if jail_name is not None:
        if not isinstance(jail_name, str):
            jail_name = str(jail_name)

        if not re.match(r"^[a-zA-Z0-9_][a-zA-Z0-9_-]*$", jail_name):
            raise director.exceptions.InvalidSpec(f"{_id} (name / #{nro}): Jail name is incorrect.")

    makejail = service.get("makejail")

    if makejail is not None and not isinstance(makejail, str):
        makejail = str(makejail)

    reset_options = service.get("reset_options")

    if reset_options is not None and not isinstance(reset_options, bool):
        raise director.exceptions.InvalidSpec(f"{_id} (reset_options / #{nro}): Must be a Boolean.")

    ignore_mtime = service.get("ignore_mtime")

    if ignore_mtime is not None and not isinstance(ignore_mtime, bool):
        raise director.exceptions.InvalidSpec(f"{_id} (ignore_mtime / #{nro}): Must be a Boolean.")

    options = service.get("options")

    if options is not None:
        __check_generic_list(options, f"{_id}/options")

    arguments = service.get("arguments")

    if arguments is not None:
        __check_generic_list(arguments, f"{_id}/arguments", False)

    environment = service.get("environment")

    if environment is not None:
        __check_generic_list(environment, f"{_id}/environment")

    volumes = service.get("volumes")

    if volumes is not None:
        __check_generic_list(volumes, f"{_id}/volumes", False)

    scripts = service.get("scripts")

    if scripts is not None:
        __check_scripts(scripts, name)

    start = service.get("start")

    if start is not None:
        __check_generic_list(start, f"{_id}/start", False)

    serial = service.get("serial")

    if serial is not None and not isinstance(serial, int):
        raise director.exceptions.InvalidSpec(f"{_id} (serial / #{nro}): Must be an Integer.")

def __check_volumes(volumes):
    if not isinstance(volumes, dict):
        raise director.exceptions.InvalidSpec("volumes: Must be a Mapping.")

    for nro, name in enumerate(volumes, 1):
        if not isinstance(name, str):
            name = str(name)

        __check_volume(volumes[name], name, nro)

def __check_volume(volume, name, nro):
    _id = f"volumes/{name}"

    device = volume.get("device")

    if device is None:
        raise director.exceptions.InvalidSpec(f"{_id} (device / #{nro}): Value required but not defined.")

    if not isinstance(device, str):
        device = str(device)

    type_ = volume.get("type")

    if type_ is not None and not isinstance(type_, str):
        type_ = str(type_)

    options = volume.get("options")

    if options is not None and not isinstance(options, str):
        options = str(options)

    dump = volume.get("dump")

    if dump is not None and not isinstance(dump, int):
        raise director.exceptions.InvalidSpec(f"{_id} (dump / #{nro}): Must be an Integer.")

    pass_ = volume.get("pass")

    if pass_ is not None and not isinstance(pass_, int):
        raise director.exceptions.InvalidSpec(f"{_id} (pass / #{nro}): Must be an Integer.")

def __check_scripts(scripts, name):
    if not isinstance(scripts, list):
        raise director.exceptions.InvalidSpec(f"scripts: Must be a List.")

    for nro, script in enumerate(scripts, 1):
        if not isinstance(script, dict):
            raise director.exceptions.InvalidSpec(f"scripts (#{nro}): Must be a Mapping.")

        __check_script(script, name, nro)

def __check_script(script, name, nro):
    _id = f"services/{name}/scripts"

    shell = script.get("shell")

    if not isinstance(shell, str):
        shell = str(shell)

    type_ = script.get("type")

    if type_ is not None:
        if not isinstance(type_, str):
            type_ = str(type_)

        if type_ not in ("jexec", "local", "chroot"):
            raise director.exceptions.InvalidSpec(f"{_id} (type / #{nro}): Only jexec, local and chroot can be used.")

    text = script.get("text")

    if text is None:
        raise director.exceptions.InvalidSpec(f"{_id} (text / #{nro}): Value required but not defined.")

    if not isinstance(text, str):
        text = str(text)

def __check_generic_list(l, n, allow_none=True):
    if not isinstance(l, list):
        raise director.exceptions.InvalidSpec(f"{n}: Must be a List.")

    for nro, e in enumerate(l, 1):
        if not isinstance(e, dict):
            raise director.exceptions.InvalidSpec(f"{n} (#{nro}): Must be a Mapping.")

        if len(e) != 1:
            raise director.exceptions.InvalidSpec(f"{n} (#{nro}): Invalid length. Must have only one element.")

        key, value = tuple(e.items())[0]

        if not isinstance(key, str):
            key = str(key)

        if not allow_none and value is None:
            raise director.exceptions.InvalidSpec(f"{n} ({key} / #{nro}): Value required but not defined.")

        if value is not None and not isinstance(value, str):
            value = str(value)
