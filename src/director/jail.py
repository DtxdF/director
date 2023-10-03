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
import shlex
import shutil
import subprocess

import director.default
import director.exceptions

def cmd(jail, text, shell="/bin/sh -c", type="jexec", output=None):
    if type not in ["jexec", "local", "chroot"]:
        raise director.exceptions.InvalidCmdType(f"{type}: Invalid command type.")

    cmd = [
        get_appjail_script(), "cmd", type, jail, "--"
    ]

    cmd.extend(shlex.split(shell))
    cmd.append(text)

    return _run(cmd, output)

def enable_start(jail, output=None, arguments=[]):
    cmd = [
        get_appjail_script(), "enable", jail, "start"
    ]

    for argument in arguments:
        arg_name, arg_val = __ydict2tuple(argument)

        cmd.extend(["-s", f"{arg_name}={arg_val}"])

    return _run(cmd, output)

def start(jail, output=None):
    return _run([
        get_appjail_script(), "start",
        "--", jail
    ], output)

def stop(jail, output=None):
    return _run([
        get_appjail_script(), "stop",
        "--", jail
    ], output)

def destroy(jail, output=None, remove_recursive=False, remove_force=True):
    cmd = [
        get_appjail_script(), "jail", "destroy"
    ]

    if remove_recursive:
        cmd.append("-R")

    if remove_force:
        cmd.append("-f")

    cmd.extend(["--", jail])

    return _run(cmd, output)

def check(jail, output=None):
    if output is None:
        output = subprocess.DEVNULL

    return _run([
        get_appjail_script(), "jail", "get",
        "--", jail, "name"
    ], output)

def status(jail, output=None):
    if output is None:
        output = subprocess.DEVNULL

    return _run([
        get_appjail_script(), "status", "-q",
        "--", jail
    ], output)

def is_dirty(jail):
    cmd = [
        get_appjail_script(), "jail", "get",
        "--", jail, "dirty"
    ]

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    if proc.returncode == 0:
        return int(proc.stdout)
    else:
        return proc.returncode

def makejail(jail, makejail, output=None, arguments=[], environment=[], volumes=(), options=[]):
    cmd = [
        get_appjail_script(), "makejail",
        "-j", jail,
        "-f", makejail
    ]

    # Environment.

    for env in environment:
        env_key, env_val = __ydict2tuple(env)

        if env_val is None:
            cmd.extend(["-V", env_key])
        else:
            cmd.extend(["-V", f"{env_key}={env_val}"])

    # Volumes.

    if volumes:
        jail_volumes = volumes[0]
        global_volumes = volumes[1]

        for jail_volume in jail_volumes:
            name, mountpoint = __ydict2tuple(jail_volume)

            volume = global_volumes.get(name)

            if volume is None:
                raise director.exceptions.VolumeNotFound(f"{name}: Volume not found.")

            device = volume["device"]
            type_ = volume.get("type", director.default.FSTAB_TYPE)

            if type_ == "nullfs":
                if not os.path.exists(device):
                    os.makedirs(device, exist_ok=True)

                device = os.path.realpath(device)
            elif type_ == "<pseudofs>":
                if not os.path.exists(device):
                    os.makedirs(device, exist_ok=True)

                device = os.path.realpath(device)

            device = device.replace('"', r'\"')
            mountpoint = mountpoint.replace('"', r'\"')
            type_ = type_.replace('"', r'\"')
            volume_options = volume.get("options", director.default.FSTAB_OPTIONS).replace('"', r'\"')
            dump = volume.get("dump", director.default.FSTAB_DUMP)
            pass_ = volume.get("pass", director.default.FSTAB_PASS)

            cmd.extend(["-o", f'fstab="{device}" "{mountpoint}" "{type_}" "{volume_options}" {dump} {pass_}'])

    # Options.

    for option in options:
        opt_name, opt_val = __ydict2tuple(option)

        if opt_val is None:
            cmd.extend(["-o", opt_name])
        else:
            cmd.extend(["-o", f"{opt_name}={opt_val}"])

    # Arguments.

    if arguments:
        cmd.append("--")

    for argument in arguments:
        arg_name, arg_val = __ydict2tuple(argument)

        if arg_val is None:
            cmd.extend([f"--{arg_name}"])
        else:
            cmd.extend([f"--{arg_name}", arg_val])

    # Profit!

    return _run(cmd, output)

def __ydict2tuple(d):
    return tuple(d.items())[0]

def _run(args, output=None):
    return subprocess.call(
        args,
        stdout=output,
        stderr=output
    )

def get_appjail_script():
    if os.getuid() == 0:
        appjail = shutil.which("appjail")
    else:
        appjail = shutil.which("appjail-user")

    if appjail is None:
        raise AppJailScriptNotFound("AppJail script not found.")

    return appjail
