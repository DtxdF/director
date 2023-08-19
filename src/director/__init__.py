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

import atexit
import os
import pathlib
import shutil
import sys
import time
import traceback
import click
import director.check
import director.config
import director.makejail
import director.random
import director.schema
from director.sysexits import *

CONFIG_FILE = os.path.join(sys.prefix, "etc/director.ini")
CONFIG = None
LOG_TIME = time.strftime("%Y-%m-%d_%Hh%Mm%Ss")
DIRECTOR_YML = "appjail-director.yml"

@click.group()
@click.help_option()
@click.version_option()
@click.option("-c", "--config", help=f"Configuration file.")
def cli(config):
    global CONFIG

    if shutil.which("appjail") is None:
        print("AppJail script not found. Cannot continue ...", file=sys.stderr)
        return EX_UNAVAILABLE

    CONFIG = director.config.Config()

    if config is None and os.path.isfile(CONFIG_FILE):
        CONFIG.read(CONFIG_FILE)
    elif config is not None:
        CONFIG.read(config)

@cli.command(short_help="Create a project")
@click.help_option()
@click.option("-f", "--file", default=f"{DIRECTOR_YML}", show_default=True, help="Specify an alternate director file.")
@click.option("-p", "--project", default=lambda: director.random.project_name(), help="Specify an alternate project name. If none is specified, a random name is used.")
def up(file, project):
    """
    Reads a director file.

    Any access to a file or directory specified in the Director file is relative
    to it, not to the current directory in which AppJail Director is running.
    
    The file specified by `--file` is copied as a read-only file. That file is
    used for further operations, specifically to make some assumptions when
    the file specified by `--file` is read back.

    When the file specified by `--file` is read, only the Makejails of the
    differing jails are executed.

    If a jail is removed from the file specified by `--file`, that jail will be
    removed from the system. Be careful when using ZFS as the datasets and all
    dependents will be forcibly removed.

    If the jail name is explicitly set and is removed, the old name is retained
    and no random name is used for subsequent operations.

    The service name and the jail name are not the same. The jail name should be
    unique, the service name should not. It is recommended to set the jail name
    only when it is really necessary. 

    After performing the initial operations, such as running the Makejail, the
    jail will be started if it is not already started.
    """

    if not director.check.project(project):
        print(f"{project}: invalid project name.", file=sys.stderr)
        return EX_DATAERR

    if not os.path.isfile(file):
        print(f"{file}: YAML file cannot be found.", file=sys.stderr)
        return EX_NOINPUT

    logsdir = f"{CONFIG.logsdir}/{project}/{LOG_TIME}"

    print("Starting Director;", f"project ID: {project};", f"logs: {logsdir};")

    projectdir = f"{CONFIG.projectsdir}/{project}"

    _check_lock(projectdir)
    atexit.register(director.makejail.unlock, projectdir)
    director.makejail.lock(projectdir)

    director_file = f"{projectdir}/{DIRECTOR_YML}"

    try:
        # Make sure that any access to any other file will be relative to the
        # Director file.
        os.chdir(os.path.join(".", os.path.dirname(file)))

        if os.path.isfile(director_file):
            old = director.makejail.convert(director_file,
                                            projectdir=projectdir,
                                            check_volume=False)
            new = director.makejail.convert(file,
                                            projectdir=projectdir)

            toremove = (x for x in old if x not in new)

            for command in toremove:
                service = command["service"]
                name = command["name"]

                director.makejail.destroy(name, logdir=f"{logsdir}/{service}/jails/{name}")

            tocreate = []

            for command in new:
                service = command["service"]
                name = command["name"]
                servicedir = f"{projectdir}/{service}"

                if command not in old \
                   or director.makejail.check(name) != 0 \
                   or director.makejail.has_failed(servicedir):
                       tocreate.append(command)

        else:
            tocreate = director.makejail.convert(file,
                                                 projectdir=projectdir)
            new = tocreate

        os.makedirs(projectdir, exist_ok=True)
        
        if os.path.isfile(director_file):
            os.remove(director_file)

        shutil.copyfile(file, director_file)

        os.chmod(director_file, 0o440)

        returncode = 0

        show_id = False

        for command in tocreate:
            service = command["service"]
            servicedir = f"{projectdir}/{service}"

            show_id = True

            returncode = director.makejail.run(command,
                                               logdir=logsdir)

            if returncode != 0:
                director.makejail.set_failed(servicedir)

                return returncode
            else:
                director.makejail.unset_failed(servicedir)

        for command in new:
            service = command["service"]
            name = command["name"]
            servicedir = f"{projectdir}/{service}"
            logdir=f"{logsdir}/{service}/jails/{name}"

            if director.makejail.status(name) == 1:
                show_id = True

                returncode = director.makejail.start(name, logdir=logdir)

                if returncode != 0:
                    director.makejail.set_failed(servicedir)

                    return returncode
                else:
                    director.makejail.unset_failed(servicedir)

        if show_id:
            print("Finished:", project)
        else:
            print("Nothing to do.")
    except Exception as err:
        print("Exception:", err, file=sys.stderr)

        os.makedirs(logsdir, exist_ok=True)
        
        with open(f"{logsdir}/exception.log", "w") as exc_fd:
            traceback.print_exc(file=exc_fd)

        return EX_SOFTWARE

    return 0

@cli.command(short_help="Stop a project")
@click.help_option()
@click.option("-d", "--destroy", is_flag=True, default=False, help="Destroy the project after stopping it.")
@click.option("-p", "--project", required=True, help="Project name.")
def down(destroy, project):
    """
    Stops the project and if the `--destroy` flag is used, it will be destroyed.
    Destroy implies stopping and destroying all the jails in that project and
    removing the project completely. Logs are not removed, you should remove
    them manually using system commands when you don't need them.
    """

    if not director.check.project(project):
        print(f"{project}: invalid project name.", file=sys.stderr)
        return EX_DATAERR

    projectdir = f"{CONFIG.projectsdir}/{project}"

    if not os.path.isdir(projectdir):
        print(f"{project}: project not found.", file=sys.stderr)
        return EX_NOINPUT

    _check_lock(projectdir)
    atexit.register(director.makejail.unlock, projectdir)
    director.makejail.lock(projectdir)

    logsdir = f"{CONFIG.logsdir}/{project}/{LOG_TIME}"

    print("Starting Director;", f"project ID: {project};", f"logs: {logsdir};")

    try:
        director_file = f"{projectdir}/{DIRECTOR_YML}"

        parsed = director.schema.Schema(file=director_file)

        services = parsed.services.keys()

        do_nothing = True

        for service in services:
            servicedir = f"{projectdir}/{service}"
            name_file = f"{servicedir}/name"

            with open(name_file) as fd:
                name = fd.readline().rstrip("\n")

            if destroy:
                do_nothing = False

                director.makejail.destroy(name, logdir=f"{logsdir}/{service}/jails/{name}")

            else:
                status_code = director.makejail.status(name)

                if status_code == 0:
                    do_nothing = False

                    director.makejail.stop(name, logdir=f"{logsdir}/{service}/jails/{name}")

        if destroy:
            do_nothing = False

            shutil.rmtree(projectdir, ignore_errors=True)

        if do_nothing:
            print("Nothing to do.")
    except Exception as err:
        print("Exception:", err, file=sys.stderr)

        os.makedirs(logsdir, exist_ok=True)
    
        with open(f"{logsdir}/exception.log", "w") as exc_fd:
            traceback.print_exc(file=exc_fd)

        return EX_SOFTWARE
    
    return 0

@cli.command(short_help="List the projects already created")
@click.help_option()
@click.option("-p", "--project", help="Project name.")
def ls(project):
    """
    Lists projects and project jails.
    """

    if project is not None:
        if not director.check.project(project):
            print(f"{project}: invalid project name.", file=sys.stderr)
            return EX_DATAERR

        projectdir = f"{CONFIG.projectsdir}/{project}"

        if not os.path.isdir(projectdir):
            print(f"{project}: project not found.", file=sys.stderr)
            return EX_NOINPUT

        logsdir = f"{CONFIG.logsdir}/{project}/{LOG_TIME}"
        
        try:
            director_file = f"{projectdir}/{DIRECTOR_YML}"

            parsed = director.schema.Schema(file=director_file)

            services = parsed.services.keys()

            if services:
                print(f"{project}:")

            for service in services:
                servicedir = f"{projectdir}/{service}"
                name_file = f"{servicedir}/name"

                with open(name_file) as fd:
                    name = fd.readline().rstrip("\n")

                status_code = director.makejail.status(name)

                if status_code == 0:
                    status = "+"
                elif status_code == 1:
                    status = "-"
                else:
                    status = "[{status_code}]"

                print(status, service, f"({name})")
        except Exception as err:
            print(f"Exception (logsdir: {logsdir}):", err, file=sys.stderr)

            os.makedirs(logsdir, exist_ok=True)
        
            with open(f"{logsdir}/exception.log", "w") as exc_fd:
                traceback.print_exc(file=exc_fd)

            return EX_SOFTWARE
    else:
        if not os.path.isdir(CONFIG.projectsdir):
            return 0

        show_header = True

        for project in pathlib.Path(CONFIG.projectsdir).iterdir():
            if show_header:
                print("Projects:")

                show_header = False

            print("-", project.name)

    return 0

def _check_lock(projectdir):
    if director.makejail.is_locked(projectdir):
        print("The project is currently locked. If you are sure that no other " \
              "instances of Director are running for this project, run " \
              f"`rm -f \"{projectdir}/lock\"`.", file=sys.stderr)
        sys.exit(EX_NOPERM)

if __name__ == "__main__":
    cli()
