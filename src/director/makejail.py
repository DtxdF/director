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
import director.random
import director.schema

class VolumeNotFound(Exception):
    """Exception thrown when a volume is not defined in volumes."""

class AppJailScriptNotFound(Exception):
    """Exception thrown when AppJail cannot be found."""

def done(projectdir):
    os.makedirs(projectdir, exist_ok=True)

    with open(f"{projectdir}/done", "w") as fd:
        pass

def is_done(projectdir):
    return os.path.isfile(f"{projectdir}/done")

def unlock(projectdir):
    lock_file = f"{projectdir}/lock"

    if os.path.isfile(lock_file):
        os.remove(lock_file)

def lock(projectdir):
    os.makedirs(projectdir, exist_ok=True)

    with open(f"{projectdir}/lock", "w") as fd:
        pass

def is_locked(projectdir):
    return os.path.isfile(f"{projectdir}/lock")

def unset_failed(servicedir):
    fail_file = f"{servicedir}/fail"

    if os.path.isfile(fail_file):
        os.remove(fail_file)

def set_failed(servicedir):
    os.makedirs(servicedir, exist_ok=True)

    with open(f"{servicedir}/fail", "w") as fd:
        pass

def has_failed(servicedir):
    return os.path.isfile(f"{servicedir}/fail")

def check(jail):
    return subprocess.call([get_appjail_script(), "jail", "get", "--", jail],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)

def status(jail):
    return subprocess.call([get_appjail_script(), "status", "-q", "--", jail],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)

def run(command, *, logdir):
    service = command["service"]
    makejail = command["makejail"]
    scripts = command["scripts"]
    start = command["start"]
    name = command["name"]

    logdir = f"{logdir}/{service}"

    os.makedirs(logdir, exist_ok=True)

    logfile_makejail = f"{logdir}/makejail.log"

    print(f"Creating {service} ({name}) ... ", end="", flush=True)

    with open(logfile_makejail, "w") as log_fd:
        process = subprocess.run(makejail,
                                 stdout=log_fd,
                                 stderr=log_fd)

        if process.returncode == 0:
            print("Done.")
        else:
            print("FAIL!")
            return process.returncode

    logfile_start = f"{logdir}/start.log"

    if start:
        with open(logfile_start, "w") as log_fd:
            print("- Start:")
            print("  -", repr(shlex.join(start)), "... ", end="", flush=True)

            process = subprocess.run(start,
                                     stdout=log_fd,
                                     stderr=log_fd)

            if process.returncode == 0:
                print("ok.")
            else:
                print("FAIL!")
                return process.returncode

    logfile_scripts = f"{logdir}/scripts.log"

    if scripts:
        print("- Scripts:")

        with open(logfile_scripts, "w") as log_fd:
            for script in scripts:
                print("  -", repr(shlex.join(script)), "... ", end="", flush=True)

                print("+", repr(script), file=log_fd)

                process = subprocess.run(script,
                                         stdout=log_fd,
                                         stderr=log_fd)

                if process.returncode == 0:
                    print("ok.")
                else:
                    print("FAIL!")
                    return process.returncode

    return 0

def start(jail, *, logdir):
    os.makedirs(logdir, exist_ok=True)

    start_log = f"{logdir}/start.log"

    print(f"Starting {jail} ... ", end="", flush=True)

    with open(start_log, "w") as log_fd:
        process = subprocess.run([get_appjail_script(), "start", "--", jail],
                                 stdout=log_fd,
                                 stderr=log_fd)

        if process.returncode == 0:
            print("Done.")
        else:
            print("FAIL!")
            return process.returncode

    return 0

def destroy(jail, *, logdir):
    returncode = status(jail)

    if returncode == 0:
        returncode = stop(jail, logdir=logdir)

        if returncode != 0:
            return returncode

    os.makedirs(logdir, exist_ok=True)

    destroy_log = f"{logdir}/destroy.log"

    print(f"Destroying {jail} ... ", end="", flush=True)

    with open(destroy_log, "w") as log_fd:
        process = subprocess.run([get_appjail_script(), "jail", "destroy", "-Rf", "--", jail],
                                 stdout=log_fd,
                                 stderr=log_fd)

        if process.returncode == 0:
            print("Done.")
        else:
            print("FAIL!")
            return process.returncode

    return 0

def stop(jail, *, logdir):
    os.makedirs(logdir, exist_ok=True)

    stop_log = f"{logdir}/stop.log"

    print(f"Stopping {jail} ... ", end="", flush=True)

    with open(stop_log, "w") as log_fd:
        process = subprocess.run([get_appjail_script(), "stop", "--", jail],
                                 stdout=log_fd,
                                 stderr=log_fd)

        if process.returncode == 0:
            print("Done.")
        else:
            print("FAIL!")
            return process.returncode

    return 0

def convert(file, *, projectdir=None, check_volume=True):
    schema_file = director.schema.Schema(file)

    global_options = __get_options(schema_file.options)

    commands = []

    for service, service_info in schema_file.services.items():
        makejail = [get_appjail_script(), "makejail"]

        servicedir = f"{projectdir}/{service}"
        name_file = f"{servicedir}/name"

        write_name = False

        if projectdir is not None and os.path.isfile(name_file):
            with open(name_file) as fd:
                name = fd.readline().rstrip("\n")

            current_name = service_info.get("name")

            if current_name is not None and name != current_name:
                write_name = True

                name = current_name
        else:
            name = service_info.get("name")

            if name is None:
                name = director.random.jail_name()

            write_name = True

        if write_name:
            os.makedirs(servicedir, exist_ok=True)

            with open(name_file, "w") as fd:
                fd.write(name)

        makejail.extend(["-j", name])

        makejail_file = ["-f", service_info.get("makejail")]

        local_options = __get_options(service_info.get("options", []))
        local_options.extend(
            __volumes2options(
                service_info.get("volumes", []),
                schema_file.volumes,
                check_volume
            )
        )
        
        reset_options = service_info.get("reset_options", False)
        
        all_options = []

        if not reset_options:
            all_options.extend(global_options)

        all_options.extend(local_options)

        environment = __get_environment(service_info.get("environment", []))

        arguments = __get_arguments(service_info.get("arguments", []))

        makejail.extend(makejail_file)
        makejail.extend(all_options)
        makejail.extend(environment)
        makejail.extend(arguments)

        scripts = __get_scripts(service_info.get("scripts", []), name)

        start_args = service_info.get("start", [])

        start = []

        if start_args:
            start.extend([get_appjail_script(), "enable", name, "start"])
            start.extend(__get_start_arguments(start_args))

        commands.append({
            "service" : service,
            "makejail" : makejail,
            "scripts" : scripts,
            "start" : start,
            "name" : name,
            "priority" : service_info.get("priority"),
            "serial" : service_info.get("serial")
        })

    return sorted(commands, key=lambda makejail: makejail['priority'])

def __get_options(options):
    parameters = []

    for option_dict in options:
        option, value = tuple(option_dict.items())[0]

        if value is None:
            parameters.extend(["-o", f"{option}"])
        else:
            parameters.extend(["-o", f"{option}={value}"])

    return parameters

def get_appjail_script():
    if os.getuid() == 0:
        appjail = shutil.which("appjail")
    else:
        appjail = shutil.which("appjail-user")

    if appjail is None:
        raise AppJailScriptNotFound("AppJail script not found.")

    return appjail

def __volumes2options(jail_volumes, volumes, check_volume=True):
    parameters = []

    for volume_dict in jail_volumes:
        volume, mountpoint = tuple(volume_dict.items())[0]
        volume_info = volumes.get(volume)

        if volume_info is None:
            raise VolumeNotFound(f"{volume} cannot be found.")

        device = volume_info.get("device")
        type_ = volume_info.get("type")
        options = volume_info.get("options")
        dump = volume_info.get("dump")
        pass_ = volume_info.get("pass")

        if type_ == "nullfs":
            if check_volume and not os.path.isdir(device):
                os.makedirs(device, exist_ok=True)

            device = os.path.realpath(device)

        device = device.replace('"', r'\"')
        mountpoint = mountpoint.replace('"', r'\"')
        type_ = type_.replace('"', r'\"')
        options = options.replace('"', r'\"')

        parameters.extend(["-o", f'fstab="{device}" "{mountpoint}" "{type_}" "{options}" {dump} {pass_}'])

    return parameters

def __get_environment(environment):
    parameters = []

    for env_dict in environment:
        env_key, env_val = tuple(env_dict.items())[0]

        if env_val is None:
            parameters.extend(["-V", f"{env_key}"])
        else:
            parameters.extend(["-V", f"{env_key}={env_val}"])

    return parameters

def __get_arguments(arguments):
    parameters = []

    for argument in arguments:
        if not parameters:
            parameters.append("--")

        arg_name, arg_val = tuple(argument.items())[0]

        parameters.extend([f"--{arg_name}", f"{arg_val}"])

    return parameters

def __get_scripts(scripts, jail):
    parameters = []

    for script_dict in scripts:
        script = []

        script.extend([get_appjail_script(), "cmd", script_dict.get("type"), jail])
        script.extend(shlex.split(script_dict.get("shell")) + [script_dict.get("text")])

        parameters.append(script)

    return parameters

def __get_start_arguments(start_arguments):
    parameters = []

    for start_argument in start_arguments:
        arg_name, arg_val = tuple(start_argument.items())[0]

        parameters.extend(["-s", f"{arg_name}={arg_val}"])

    return parameters
