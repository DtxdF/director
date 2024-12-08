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

import copy
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

    allowed_keys = (
        "options",
        "services",
        "default_volume_type",
        "volumes",
    )

    __check_allowed_key(allowed_keys, "<main>", document)

    options = document.get("options")

    if options is not None:
        document["options"] = _fix_non_str_list(options, "options")

    services = document.get("services")

    if services is None:
        raise director.exceptions.InvalidSpec("services: Required but not defined.")
    else:
        __check_services(services)

    default_volume_type = document.get("default_volume_type")

    if default_volume_type is not None:
        if not isinstance(default_volume_type, str):
            default_volume_type = str(default_volume_type)

            document["default_volume_type"] = default_volume_type

    volumes = document.get("volumes")

    if volumes is not None:
        __check_volumes(volumes)

def __check_services(services):
    if not isinstance(services, dict):
        raise director.exceptions.InvalidSpec("services: Must be a Mapping.")

    _fix_non_str_keys(services)

    for nro, name in enumerate(services, 1):
        if not re.match(r"^[a-zA-Z0-9._-]+$", name):
            raise director.exceptions.InvalidSpec(f"services ({name} / #{nro}): Service name is incorrect.")

        service = services[name]

        if not isinstance(service, dict):
            raise director.exceptions.InvalidSpec(f"services/{name} (#{nro}): Must be a Mapping.")

        __check_service(service, name, nro)

def __check_service(service, name, nro):
    _id = f"services/{name}"

    allowed_keys = (
        "priority",
        "name",
        "makejail",
        "reset_options",
        "ignore_mtime",
        "options",
        "arguments",
        "environment",
        "start-environment",
        "oci",
        "volumes",
        "scripts",
        "start",
        "serial"
    )

    __check_allowed_key(allowed_keys, _id, service)

    priority = service.get("priority")

    if priority is not None and not isinstance(priority, int):
        raise director.exceptions.InvalidSpec(f"{_id} (priority / #{nro}): Must be an Integer.")

    jail_name = service.get("name")

    if jail_name is not None:
        if not isinstance(jail_name, str):
            jail_name = str(jail_name)

            service["name"] = jail_name

        if not re.match(r"^[a-zA-Z0-9_][a-zA-Z0-9_-]*$", jail_name):
            raise director.exceptions.InvalidSpec(f"{_id} (name / #{nro}): Jail name is incorrect.")

    makejail = service.get("makejail")

    if makejail is not None and not isinstance(makejail, str):
        makejail = str(makejail)

        service["makejail"] = makejail

    reset_options = service.get("reset_options")

    if reset_options is not None and not isinstance(reset_options, bool):
        raise director.exceptions.InvalidSpec(f"{_id} (reset_options / #{nro}): Must be a Boolean.")

    ignore_mtime = service.get("ignore_mtime")

    if ignore_mtime is not None and not isinstance(ignore_mtime, bool):
        raise director.exceptions.InvalidSpec(f"{_id} (ignore_mtime / #{nro}): Must be a Boolean.")

    options = service.get("options")

    if options is not None:
        service["options"] = _fix_non_str_list(options, f"{_id}/options")

    arguments = service.get("arguments")

    if arguments is not None:
        service["arguments"] = _fix_non_str_list(arguments, f"{_id}/arguments", False)

    environment = service.get("environment")

    if environment is not None:
        service["environment"] = _fix_non_str_list(environment, f"{_id}/environment")

    start_environment = service.get("start-environment")

    if start_environment is not None:
        service["start-environment"] = _fix_non_str_list(start_environment, f"{_id}/start-environment")

    oci = service.get("oci")

    if oci is not None:
        if not isinstance(oci, dict):
            raise director.exceptions.InvalidSpec(f"{_id} (oci / #{nro}): Must be a Mapping.")

        oci_user = oci.get("user")

        if oci_user is not None and not isinstance(oci_user, str):
            oci_user = str(oci_user)

            oci["user"] = oci_user

        oci_workdir = oci.get("workdir")

        if oci_workdir is not None and not isinstance(oci_workdir, str):
            oci_workdir = str(oci_workdir)

            oci["workdir"] = oci_workdir
        
        oci_environment = oci.get("environment")

        if oci_environment is not None:
            oci["environment"] = _fix_non_str_list(oci_environment, f"{_id}/oci/environment", False)

    volumes = service.get("volumes")

    if volumes is not None:
        service["volumes"] = _fix_non_str_list(volumes, f"{_id}/volumes", False)

    scripts = service.get("scripts")

    if scripts is not None:
        __check_scripts(service["scripts"], name)

    start = service.get("start")

    if start is not None:
        service["start"] = _fix_non_str_list(start, f"{_id}/start", False)

    serial = service.get("serial")

    if serial is not None and not isinstance(serial, int):
        raise director.exceptions.InvalidSpec(f"{_id} (serial / #{nro}): Must be an Integer.")

def __check_volumes(volumes):
    if not isinstance(volumes, dict):
        raise director.exceptions.InvalidSpec("volumes: Must be a Mapping.")

    _fix_non_str_keys(volumes)

    for nro, name in enumerate(volumes, 1):
        volume = volumes[name]

        if not isinstance(volume, dict):
            raise director.exceptions.InvalidSpec(f"volumes/{name} (#{nro}): Must be a Mapping.")

        __check_volume(volume, name, nro)

def __check_volume(volume, name, nro):
    _id = f"volumes/{name}"

    allowed_keys = (
        "device",
        "type",
        "options",
        "dump",
        "pass",
        "umask",
        "mode",
        "owner",
        "group"
    )

    __check_allowed_key(allowed_keys, _id, volume)

    device = volume.get("device")

    if device is None:
        raise director.exceptions.InvalidSpec(f"{_id} (device / #{nro}): Value required but not defined.")

    if not isinstance(device, str):
        device = str(device)

        volume["device"] = device

    type_ = volume.get("type")

    if type_ is not None and not isinstance(type_, str):
        type_ = str(type_)

        volume["type"] = type_

    options = volume.get("options")

    if options is not None and not isinstance(options, str):
        options = str(options)

        volume["options"] = options

    dump = volume.get("dump")

    if dump is not None and not isinstance(dump, int):
        raise director.exceptions.InvalidSpec(f"{_id} (dump / #{nro}): Must be an Integer.")

    pass_ = volume.get("pass")

    if pass_ is not None and not isinstance(pass_, int):
        raise director.exceptions.InvalidSpec(f"{_id} (pass / #{nro}): Must be an Integer.")

    umask = volume.get("umask")

    if umask is not None and not isinstance(umask, int):
        raise director.exceptions.InvalidSpec(f"{_id} (umask / #{nro}): Must be an Integer.")

    mode = volume.get("mode")

    if mode is not None and not isinstance(mode, int):
        raise director.exceptions.InvalidSpec(f"{_id} (mode / #{nro}): Must be an Integer.")

    owner = volume.get("owner")

    if owner is not None:
        if not isinstance(owner, int) and not isinstance(owner, str):
            raise director.exceptions.InvalidSpec(f"{_id} (owner / #{nro}): Must be an Integer or a string.")

    group = volume.get("group")

    if group is not None:
        if not isinstance(group, int) and not isinstance(group, str):
            raise director.exceptions.InvalidSpec(f"{_id} (group / #{nro}): Must be an Integer or a string.")

def __check_scripts(scripts, name):
    if not isinstance(scripts, list):
        raise director.exceptions.InvalidSpec(f"scripts: Must be a List.")

    for nro, script in enumerate(scripts, 1):
        if not isinstance(script, dict):
            raise director.exceptions.InvalidSpec(f"scripts (#{nro}): Must be a Mapping.")

        _fix_non_str_keys(script)

        __check_script(script, name, nro)

def __check_script(script, name, nro):
    _id = f"services/{name}/scripts"

    allowed_keys = (
        "shell",
        "type",
        "text"
    )

    __check_allowed_key(allowed_keys, _id, script)

    shell = script.get("shell")

    if shell is not None and not isinstance(shell, str):
        shell = str(shell)

        script["shell"] = shell

    type_ = script.get("type")

    if type_ is not None:
        if not isinstance(type_, str):
            type_ = str(type_)

            script["type"] = type_

        if type_ not in ("jexec", "local", "chroot"):
            raise director.exceptions.InvalidSpec(f"{_id} (type / #{nro}): Only jexec, local and chroot can be used.")

    text = script.get("text")

    if text is None:
        raise director.exceptions.InvalidSpec(f"{_id} (text / #{nro}): Value required but not defined.")

    if not isinstance(text, str):
        text = str(text)

        script["text"] = text

def __check_allowed_key(allowed_keys, name, data):
    for key in data:
        if key not in allowed_keys:
            raise director.exceptions.InvalidSpec(f"{name}: Unknown key \"{key}\".")

def _fix_non_str_list(data, name, allow_none=True):
    if not isinstance(data, list):
        raise director.exceptions.InvalidSpec(f"{name}: Must be a List.")

    l = []

    for nro, e in enumerate(data, 1):
        if not isinstance(e, dict):
            raise director.exceptions.InvalidSpec(f"{name} (#{nro}): Must be a Mapping.")

        if len(e) != 1:
            raise director.exceptions.InvalidSpec(f"{name} (#{nro}): Invalid length. Must have only one element.")

        key, value = tuple(e.items())[0]

        if not isinstance(key, str):
            key = str(key)

        if not allow_none and value is None:
            raise director.exceptions.InvalidSpec(f"{name} ({key} / #{nro}): Value required but not defined.")

        if value is not None and not isinstance(value, str):
            value = str(value)

        l.append({
            key : value
        })

    return l

def _fix_non_str_keys(data):
    _data = copy.deepcopy(data)

    for name in _data:
        if not isinstance(name, str):
            data[str(name)] = _data[name]
            data.pop(name)
