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
import random
import shlex
import shutil
import subprocess
import sys
import time

import director.default
import director.exceptions
from director.sysexits import *

LAST_PROC = []

def cmd(jail, text, shell="/bin/sh -c", type="jexec", output=None, timeout=None, env=None):
    if type not in ["jexec", "local", "chroot"]:
        raise director.exceptions.InvalidCmdType(f"{type}: Invalid command type.")

    cmd = [
        get_appjail_script(), "cmd", type, jail, "--"
    ]

    cmd.extend(shlex.split(shell))
    cmd.append(text)

    return _run(cmd, output, timeout, env)

def enable_start(jail, output=None, arguments=[], environment=[], timeout=None, shell_env=None):
    cmd = [
        get_appjail_script(), "enable", jail, "start"
    ]

    for argument in arguments:
        arg_name, arg_val = __ydict2tuple(argument)

        cmd.extend(["-s", f"{arg_name}={arg_val}"])

    for env_var in environment:
        env_name, env_val = __ydict2tuple(env_var)

        cmd.extend(["-V", f"{env_name}={env_val}"])

    return _run(cmd, output, timeout, shell_env)

def start(jail, output=None, timeout=None, env=None):
    return _run([
        get_appjail_script(), "start",
        "--", jail
    ], output, timeout, env)

def stop(jail, output=None, timeout=None, env=None):
    return _run([
        get_appjail_script(), "stop",
        "--", jail
    ], output, timeout, env)

def destroy(jail, output=None, remove_recursive=False, remove_force=True, timeout=None, env=None):
    cmd = [
        get_appjail_script(), "jail", "destroy"
    ]

    if remove_recursive:
        cmd.append("-R")

    if remove_force:
        cmd.append("-f")

    cmd.extend(["--", jail])

    return _run(cmd, output, timeout)

def check(jail, output=None, timeout=None, env=None):
    if output is None:
        output = subprocess.DEVNULL

    return _run([
        get_appjail_script(), "jail", "get",
        "--", jail, "name"
    ], output, timeout, env)

def status(jail, output=None, timeout=None, env=None):
    if output is None:
        output = subprocess.DEVNULL

    return _run([
        get_appjail_script(), "status", "-q",
        "--", jail
    ], output, timeout, env)

def is_dirty(jail, timeout=None, env=None):
    cmd = [
        get_appjail_script(), "jail", "get",
        "--", jail, "dirty"
    ]

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        timeout=timeout,
        env=env
    )

    if proc.stdout is None:
        return -1

    stdout = proc.stdout.strip()

    if stdout == "":
        return -1

    if stdout == "0":
        return 0
    elif stdout == "1":
        return 1
    else:
        return proc.returncode

def makejail(jail, makejail, output=None, arguments=[], environment=[], volumes=(), options=[], timeout=None, shell_env=None):
    if shell_env is None:
        shell_env = os.environ.copy()
        shell_env["GIT_ASKPASS"] = "true"

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
        default_volume_type = volumes[2]

        for jail_volume in jail_volumes:
            name, mountpoint = __ydict2tuple(jail_volume)

            volume = global_volumes.get(name)

            if volume is None:
                raise director.exceptions.VolumeNotFound(f"{name}: Volume not found.")

            device = volume["device"]
            type_ = volume.get("type", default_volume_type)

            if type_ == "nullfs" or type_ == "<pseudofs>":
                umask = volume.get("umask")

                old_umask = None

                # Get the current umask and sets the user's desired umask.
                if umask is not None:
                    old_umask = os.umask(0)

                    os.umask(umask)

                if not os.path.exists(device):
                    os.makedirs(device, exist_ok=True)

                # I know that `os.makedirs()` already has a parameter named `mode`, but it is
                # preferable this way to set the mode each time.
                mode = volume.get("mode")

                if mode is not None:
                    os.chmod(device, mode)

                owner = volume.get("owner")
                group = volume.get("group")
                
                if owner is not None or group is not None:
                    shutil.chown(device, owner, group)

                # Restore from old umask.
                if old_umask is not None:
                    os.umask(old_umask)

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

    return _run(cmd, output, timeout, shell_env, jail)

def __ydict2tuple(d):
    return tuple(d.items())[0]

def _run(args, output=None, timeout=None, env=None, jail=None):
    proc = subprocess.Popen(
        args,
        stdout=output,
        stderr=output,
        stdin=subprocess.DEVNULL,
        env=env
    )

    LAST_PROC.append(proc)

    timeout_expired = False

    try:
        proc.wait(timeout)
    except KeyboardInterrupt:
        if jail is None:
            _terminate(proc.pid)

            if proc.returncode is None or proc.returncode == 0:
                return EX_SOFTWARE
            else:
                return proc.returncode
        else:
            returncode = status(jail, timeout=timeout)

            if returncode == 0:
                returncode = stop(jail, subprocess.DEVNULL, timeout)

            _terminate(proc.pid)

            return returncode
    except subprocess.TimeoutExpired:
        timeout_expired = True

        _terminate(proc.pid)

    returncode = proc.returncode

    if timeout_expired and returncode == 0:
        returncode = EX_SOFTWARE

    return returncode

def _terminate(pid):
    return subprocess.call([get_appjail_script(), "cmd", "jaildir", "kill", "--", f"{pid}"],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)

def get_appjail_script():
    appjail = shutil.which("appjail")

    if appjail is None:
        raise AppJailScriptNotFound("AppJail script not found.")

    return appjail
