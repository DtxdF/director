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
import json
import os
import pathlib
import shutil
import signal
import subprocess
import sys
import traceback
from signal import (SIGALRM,
                   SIGVTALRM,
                   SIGPROF,
                   SIGUSR1,
                   SIGUSR2,
                   SIGHUP,
                   SIGINT,
                   SIGQUIT,
                   SIGTERM,
                   SIGXCPU,
                   SIGXFSZ)

import click
import dotenv

import director.config
import director.default
import director.jail
import director.log
import director.project
from director.sysexits import *

CURRENT_JAIL = None

# Signals.
IGNORED_SIGNALS = (SIGALRM, SIGVTALRM, SIGPROF, SIGUSR1, SIGUSR2)
HANDLER_SIGNALS = (SIGHUP, SIGINT, SIGQUIT, SIGTERM, SIGXCPU, SIGXFSZ)

@click.group()
@click.help_option()
@click.version_option()
@click.option("-c", "--config", help="Configuration file.")
@click.option("-e", "--env-file", default=director.default.ENV_FILE, help="Specify an alternate file to load environment variables.")
def cli(config, env_file):
    """
    AppJail Director is a tool for running multi-jail environments on AppJail using a
    simple YAML specification. A Director file is used to define how one or more jails
    that make up your application are configured. Once you have a Director file, you
    can create and start your application with a single command: `appjail-director up`.

    The configuration files are loaded in the following order: prefix/etc/director.ini,
    ~/.director/director.ini, from the environment variable DIRECTOR_CONFIG and from
    the --config option. Only the first two are loaded if they exist, otherwise they
    are ignored. When specifying the configuration file from the environment variable
    or from the command-line option, you must be sure that these files exist, otherwise
    an error will be displayed.

    An environment file specified by --env-file is loaded if it exists, otherwise it is
    ignored. This file is very useful for when you need to put some secrets or some
    dynamic values in your Director file but they should not be in it and probably
    not in a repository either.
    """

    # Load environment from a file.
    dotenv.load_dotenv(env_file)
    
    # Config.

    required_config_files = []

    default_config_files = director.default.CONFIG_FILES

    # From an environment variable.

    env_config_file = os.getenv("DIRECTOR_CONFIG")

    if env_config_file is not None:
        required_config_files.append(env_config_file)

    # From CLI.

    if config is not None:
        required_config_files.append(config)

    for config_file in required_config_files:
        if not os.path.isfile(config_file):
            print(f"{config_file}: Configuration file does not exist.", file=sys.stderr)
            sys.exit(EX_NOINPUT)

    # Merge existing required with defaults.
    default_config_files.extend(required_config_files)

    for config_file in default_config_files:
        if os.path.isfile(config_file):
            try:
                director.config.load(config_file)
            except Exception as err:
                print(f"{config_file}: Exception while loading the configuration file: {err}")
                sys.exit(EX_CONFIG)

@cli.command(short_help="Create a project")
@click.help_option()
@click.option("-f", "--file", default=director.default.DIRECTOR_FILE, show_default=True, help="Specify an alternate director file.")
@click.option("-p", "--project", help="Specify an alternate project name. If none is specified, a random name is used.")
@click.option("--overwrite", is_flag=True, default=False, help="Re-create all services, even when it is not necessary.")
def up(file, project, overwrite):
    """
    Reads a director file.

    Any access to a file or directory specified in the Director file is relative
    to it, not to the current directory in which AppJail Director is running.

    When a Director file specified by --file is read, Director will perform
    some checks to verify if it needs to create or recreate a service.

    The checks that Director performs are: overwrite, differing, failed, mtime
    and differing_options. overwrite will recreate the service if the --overwrite 
    option is specified. differing will recreate the service if it differs from
    the old file that is copied each time the up command is executed. failed will
    recreate the service if it has previously failed in some way (e.g. creating
    or starting it). mtime will recreate the service if the Makejail modification
    time differs from the old one, but if ignore_mtime is specified this does not
    apply. differering_options will recreate the service if the global options
    change from the previous one, but if reset_options is true, it is ignored.
    Of course, if a service does not exist, Director will create it. A service is
    also created if the project is new (does not exist previously).

    By default, when a project name is not specified using the --project option,
    Director tries to read the DIRECTOR_PROJECT environment variable and, if it is
    not set, a random name is chosen.

    When removing a service (specifically, the jail), the remove_force and
    remove_recursive options specified from the configuration file determine the
    behavior of this action. 
    """

    ignore_other_signals()
    enable_stop_jail_handler()

    if project is None:
        project = _get_project_name_from_env(director.project.generate_random_name())

    if not os.path.isfile(file):
        print(f"{file}: Director file cannot be found.", file=sys.stderr)
        sys.exit(EX_NOINPUT)

    log = director.log.Log(
        basedir=director.config.get("logs", "directory")
    )

    print(f"Starting Director (project:{project}) ...")

    try:
        # Make sure that any access to any other file will be relative to the
        # Director file.
        os.chdir(os.path.join(".", os.path.dirname(file)))

        # Destroying behavior.
        remove_recursive = director.config.getboolean("jails", "remove_recursive")
        remove_force = director.config.getboolean("jails", "remove_force")

        # Command timeout.
        command_timeout = director.config.getint("commands", "timeout")

        do_nothing = True

        projectsdir = director.config.get("projects", "directory")

        with director.project.Project(project, file, projectsdir) as project_obj:
            # Initial state.
            project_obj.set_state(director.project.STATE_UNFINISHED)

            order = []

            services = project_obj.get_services()
            
            toremove = project_obj.get_removed()
            
            # Differ & Order.
            for service in services:
                if overwrite or \
                        project_obj.differ(service) or \
                        project_obj.has_failed(service) or \
                        (not project_obj.ignore_mtime(service) and \
                            project_obj.check_makejail_mtime(service)) or \
                        (not project_obj.reset_options(service) and \
                            project_obj.differ_options()):
                    toremove.add(service)

                order.append({
                    "priority" : project_obj.get_priority(service),
                    "service" : service
                })

            # Remove.
            for service in toremove:
                jail = project_obj.get_jail_name(service)

                if director.jail.check(jail) == 0:
                    do_nothing = False

                    # To be reliable, the last log must be set before creating a log file. It is not
                    # a good idea to do this at the start of the context manager as we lie to the
                    # user since no log can be created in the execution of this code and the
                    # following ones.
                    project_obj.set_key("last_log", log.directory)

                    if director.jail.status(jail) == 0:
                        with log.open(os.path.join(service, "stop.log")) as fd:
                            print(f"Stopping {service} ({jail}) ...", end=" ", flush=True)

                            returncode = director.jail.stop(jail, fd, command_timeout)

                            if returncode == 0:
                                print("Done.")
                            else:
                                print("FAIL!")

                    with log.open(os.path.join(service, "destroy.log")) as fd:
                        print(f"Destroying {service} ({jail}) ...", end=" ", flush=True)

                        returncode = director.jail.destroy(
                            jail, fd, remove_recursive,
                            remove_force
                        )

                        if returncode == 0:
                            print("Done.")

                            # Remove service information if it is no longer really needed.
                            if service not in services:
                                project_obj.unset_key(service)
                        else:
                            print("FAIL!")
                            project_obj.set_state(director.project.STATE_FAILED)
                            project_obj.set_fail(service)
                            sys.exit(returncode)

            global_volumes = project_obj.get_volumes()

            # Create.
            for service_dict in sorted(order, key=lambda s: s["priority"]):
                service = service_dict["service"]

                use_random_name = False

                try:
                    last_jname = project_obj.get_jail_name(service, where="current")
                except director.exceptions.ServiceNotFound:
                    last_jname = None
                    use_random_name = True

                try:
                    next_jname = project_obj.get_jail_name(service,
                                                           where="next",
                                                           random_name=use_random_name,
                                                           cached=False)
                except director.exceptions.ServiceNotFound:
                    next_jname = None

                if next_jname is None:
                    jail = last_jname
                elif next_jname != last_jname:
                    jail = next_jname
                else:
                    jail = next_jname

                set_current_jail(jail)

                if director.jail.check(jail) != 0 or \
                        director.jail.is_dirty(jail) != 0:
                    do_nothing = False

                    options = []

                    if not project_obj.reset_options(service):
                        options.extend(project_obj.get_options())

                    options.extend(project_obj.get_local_options(service))

                    arguments = project_obj.get_arguments(service)

                    environment = project_obj.get_environment(service)

                    volumes = (
                        project_obj.get_jail_volumes(service),
                        global_volumes,
                        project_obj.get_default_volume_type() or \
                                director.default.FSTAB_TYPE
                    )

                    makejail = project_obj.get_makejail(service)

                    # Makejail modification time.
                    project_obj.set_makejail_mtime(service)

                    # Last log.
                    project_obj.set_key("last_log", log.directory)

                    with log.open(os.path.join(service, "makejail.log")) as fd:
                        print(f"Creating {service} ({jail}) ...", end=" ", flush=True)

                        returncode = director.jail.makejail(
                            jail, makejail, fd, arguments,
                            environment, volumes, options,
                            command_timeout
                        )

                        if returncode == 0:
                            print("Done.")
                        else:
                            print("FAIL!")
                            project_obj.set_state(director.project.STATE_FAILED)
                            project_obj.set_fail(service)
                            sys.exit(returncode)

                    # Start arguments & environment.

                    start_arguments = project_obj.get_start_arguments(service)
                    start_environment = project_obj.get_start_environment(service)

                    if start_arguments or start_environment:
                        with log.open(os.path.join(service, "enable-start.log")) as fd:
                            print("", "- Setting up start arguments ...", end=" ", flush=True)

                            returncode = director.jail.enable_start(jail, fd,
                                                                    start_arguments,
                                                                    start_environment)

                            if returncode == 0:
                                print("Done.")
                            else:
                                print("FAIL!")

                    # Scripts.

                    scripts = project_obj.get_scripts(service)

                    if scripts:
                        with log.open(os.path.join(service, "scripts.log")) as fd:
                            print("- Scripts:")

                            for script in scripts:
                                text = script["text"]
                                shell = script.get("shell", director.default.SHELL)
                                type_ = script.get("type", director.default.SHELL_TYPE)

                                _repr_text = repr(text)
                                _end = " "

                                for out in (sys.stdout, fd):
                                    print("", f"- (type: {type_}, shell: {shell}):", _repr_text, "...",
                                          end=_end, file=out, flush=True)

                                    _end = "\n"

                                returncode = director.jail.cmd(
                                    jail, text, shell, type_, fd,
                                    command_timeout
                                )

                                if returncode == 0:
                                    print("ok.")
                                else:
                                    print("FAIL!")
                                    project_obj.set_state(director.project.STATE_FAILED)
                                    project_obj.set_fail(service)
                                    sys.exit(returncode)

                if director.jail.status(jail) != 0:
                    do_nothing = False

                    # Last log.
                    project_obj.set_key("last_log", log.directory)

                    with log.open(os.path.join(service, "start.log")) as fd:
                        print(f"Starting {service} ({jail}) ...", end=" ", flush=True)

                        returncode = director.jail.start(
                            jail, fd, command_timeout
                        )

                        if returncode == 0:
                            print("Done.")
                        else:
                            print("FAIL!")
                            project_obj.set_state(director.project.STATE_FAILED)
                            project_obj.set_fail(service)
                            sys.exit(returncode)

                project_obj.set_done(service)

            # Done.
            project_obj.set_state(director.project.STATE_DONE)

            if do_nothing:
                print("Nothing to do.")
            else:
                print("Finished:", project)
    except Exception as err:
        _catch(log, err)

        sys.exit(EX_SOFTWARE)

    sys.exit(EX_OK)

def stop_jail_handler(*args, **kwargs):
    if CURRENT_JAIL is None:
        sys.exit(0)

    disable_stop_jail_handler()

    try:
        timeout = director.config.getint("commands", "timeout")
    except Exception as err:
        print_err(err)

        # fallback
        timeout = director.config.__DEFAULT_CONFIG__.get("commands", "timeout")

    if director.jail.status(CURRENT_JAIL, timeout=timeout) == 0:
        director.jail.stop(CURRENT_JAIL, subprocess.DEVNULL, timeout)
    
    for proc in director.jail.LAST_PROC:
        if proc.poll() is not None:
            continue

        director.jail._terminate(proc.pid)

        try:
            proc.wait(timeout)
        except subprocess.TimeoutExpired:
            pass # ignore
        except Exception as err:
            print_err(err)

    sys.exit(EX_SOFTWARE)

def enable_stop_jail_handler():
    for signum in HANDLER_SIGNALS:
        signal.signal(signum, stop_jail_handler)

def disable_stop_jail_handler():
    for signum in HANDLER_SIGNALS:
        signal.signal(signum, signal.SIG_IGN)

def ignore_other_signals():
    for signum in IGNORED_SIGNALS:
        signal.signal(signum, signal.SIG_IGN)

def set_current_jail(jail):
    global CURRENT_JAIL

    CURRENT_JAIL = jail

@cli.command(short_help="Stop and/or destroy a project")
@click.help_option()
@click.option("-d", "--destroy", is_flag=True, default=False, help="Destroy the project after stopping it.")
@click.option("-p", "--project", help="Project name.")
@click.option("--ignore-failed", is_flag=True, default=False, help="Ignore services that are not destroyed.")
@click.option("--ignore-services", is_flag=True, default=False, help="Ignore services.")
def down(destroy, project, ignore_failed, ignore_services):
    """
    Stops the project and if the --destroy flag is used, it will be destroyed.
    Destroy implies stopping and destroying all the jails in that project and
    removing the project completely. Logs are not removed, you should remove
    them manually using system commands when you don't need them.

    The project name is obtained from the command-line option and, if not set,
    from the DIRECTOR_PROJECT environment variable.
    """

    if project is None:
        project = _get_project_name_from_env()

        if project is None:
            __project_name_not_specified()
            sys.exit(EX_DATAERR)

    log = director.log.Log(
        basedir=director.config.get("logs", "directory")
    )

    print(f"Starting Director (project:{project}) ...")

    try:
        do_nothing = True

        projectsdir = director.config.get("projects", "directory")

        # Destroying behavior.
        remove_recursive = director.config.getboolean("jails", "remove_recursive")
        remove_force = director.config.getboolean("jails", "remove_force")

        # Command timeout.
        command_timeout = director.config.getint("commands", "timeout")

        # We cannot use a context manager because it calls the .open() method which fails
        # since no `director` file has been defined.
        project_obj = director.project.Project(project, basedir=projectsdir)

        if not os.path.isdir(project_obj.directory):
            print(f"{project}: Project not found.", file=sys.stderr)
            sys.exit(EX_NOINPUT)

        project_obj.lock()

        atexit.register(project_obj.unlock)

        project_obj.set_state(director.project.STATE_DESTROYING)

        if not ignore_services:
            services = project_obj.get_services(next=False)

            order = []

            for service in services:
                order.append({
                    "priority" : project_obj.get_priority(service, next=False),
                    "service" : service
                })

            for service_dict in sorted(order, key=lambda s: s["priority"], reverse=True):
                service = service_dict["service"]
                jail = project_obj.get_jail_name(service, where="current")

                status = director.jail.status(jail)

                if status == 0:
                    do_nothing = False

                    print(f"Stopping {service} ({jail}) ...", end=" ", flush=True)

                    returncode = director.jail.stop(jail, subprocess.DEVNULL, command_timeout)

                    if returncode == 0:
                        print("Done.")
                    else:
                        print("FAIL!")

                if destroy:
                    do_nothing = False

                    print(f"Destroying {service} ({jail}) ...", end=" ", flush=True)

                    returncode = director.jail.destroy(
                        jail, subprocess.DEVNULL,
                        remove_recursive, remove_force
                    )

                    if returncode == 0:
                        print("Done.")
                    else:
                        print("FAIL!")

                        if not ignore_failed:
                            sys.exit(returncode)

        if destroy:
            do_nothing = False

            print(f"Destroying {project} ...", end=" ", flush=True)

            shutil.rmtree(project_obj.directory, ignore_errors=True)

            print("Done.")

        if do_nothing:
            print("Nothing to do.")
    except Exception as err:
        _catch(log, err)

        sys.exit(EX_SOFTWARE)
    
    sys.exit(EX_OK)

@cli.command(short_help="List projects")
@click.help_option()
@click.option("-s", "--state", default=director.project.STATES, multiple=True, show_default=True, help="Project status. Ignored when using --project. Can be specified several times.")
def ls(state):
    """
    Lists projects.

    In addition to simply displaying the project name, the current status
    of the project is shown symbolically on the left side as follows:
    + (DONE), - (FAILED), ! (UNFINISHED), x (DESTROYING), ? (UNKNOWN).
    """

    # From the source code, this name makes more sense.
    states = state

    projectsdir = director.config.get("projects", "directory")

    if not os.path.isdir(projectsdir):
        print("No project has been created.")
        sys.exit(EX_OK)

    # Only to inform the user.
    invalid_state = None

    # State check.
    try:
        for _state in states:
            # Last state before the exception is thrown.
            invalid_state = _state

            # The check.
            director.project.STATES.index(_state)
    except ValueError:
        print(f"{invalid_state}: Invalid state.", file=sys.stderr)
        sys.exit(EX_DATAERR)

    show_header = True

    do_nothing = True

    for project in pathlib.Path(projectsdir).iterdir():
        do_nothing = False

        project_obj = director.project.Project(project.name, basedir=projectsdir)

        project_state = project_obj.get_state()

        # Fallback.
        if project_state is None:
            project_state = director.project.STATES[director.project.STATE_UNFINISHED]
        
        # Match?
        match = False

        for _state in states:
            if _state == project_state:
                match = True
                break

        # Ignore.
        if not match:
            continue

        if show_header:
            print("Projects:")

            show_header = False

        if _state == director.project.STATES[director.project.STATE_DONE]:
            state_symbol = "+"
        elif _state == director.project.STATES[director.project.STATE_FAILED]:
            state_symbol = "-"
        elif _state == director.project.STATES[director.project.STATE_UNFINISHED]:
            state_symbol = "!"
        elif _state == director.project.STATES[director.project.STATE_DESTROYING]:
            state_symbol = "x"
        else:
            state_symbol = "?"

        print("", state_symbol, project.name)

    if do_nothing:
        print("No project has been created.")

    sys.exit(EX_OK)

@cli.command(short_help="Show information about a project")
@click.help_option()
@click.option("-p", "--project", help="Project name.")
def info(project):
    """
    Show information about a project.

    In addition to displaying the services, the current status of each service
    is shown symbolically on the left side as follows: + (RUNNING), - (STOPPED),
    ! (FAILED). In addition for !, the status code will be displayed.

    The project name is obtained from the command-line option and, if not set,
    from the DIRECTOR_PROJECT environment variable.
    """

    if project is None:
        project = _get_project_name_from_env()

        if project is None:
            __project_name_not_specified()
            sys.exit(EX_DATAERR)

    log = director.log.Log(
        basedir=director.config.get("logs", "directory")
    )

    try:
        projectsdir = director.config.get("projects", "directory")

        project_obj = director.project.Project(project, basedir=projectsdir)

        if not os.path.isdir(project_obj.directory):
            print(f"{project}: Project not found.", file=sys.stderr)
            sys.exit(EX_NOINPUT)

        state = project_obj.get_state()

        # Fallback.
        if state is None:
            state = director.project.STATES[director.project.STATE_UNFINISHED]

        # This looks better.
        state = state.upper()

        last_log = project_obj.get_key("last_log") or "none"

        if project_obj.locked():
            locked = "true"
        else:
            locked = "false"

        services = project_obj.get_services(next=False)

        print(f"{project}:")
        print("", "state:", state)
        print("", "last log:", last_log)
        print("", "locked:", locked)
        print("", "services:")

        for service in services:
            jail = project_obj.get_jail_name(service, where="current")

            status = director.jail.status(jail)

            if status == 0:
                status_symbol = "+"
            elif status == 1:
                status_symbol = "-"
            else:
                status_symbol = "!"

            print(" ", f"{status_symbol} {service} ({jail})", end="")

            if status > 1:
                print(f" [{status}]")
            else:
                print()
    except Exception as err:
        _catch(log, err)

        sys.exit(EX_SOFTWARE)
    
    sys.exit(EX_OK)

@cli.command(short_help="Show information about a project in JSON format")
@click.help_option()
@click.option("-p", "--project", help="Project name.")
def describe(project):
    """
    Like `info` but in JSON format.
    """

    if project is None:
        project = _get_project_name_from_env()

        if project is None:
            __project_name_not_specified()
            sys.exit(EX_DATAERR)

    log = director.log.Log(
        basedir=director.config.get("logs", "directory")
    )

    try:
        projectsdir = director.config.get("projects", "directory")

        project_obj = director.project.Project(project, basedir=projectsdir)

        if not os.path.isdir(project_obj.directory):
            print(f"{project}: Project not found.", file=sys.stderr)
            sys.exit(EX_NOINPUT)

        state = project_obj.get_state()

        # Fallback.
        if state is None:
            state = director.project.STATES[director.project.STATE_UNFINISHED]

        # This looks better.
        state = state.upper()

        last_log = project_obj.get_key("last_log") or None

        if project_obj.locked():
            locked = True
        else:
            locked = True

        output = {
            "name" : project,
            "state" : state,
            "last_log" : last_log,
            "locked" : locked,
            "services" : []
        }

        services = project_obj.get_services(next=False)

        for service in services:
            jail = project_obj.get_jail_name(service, where="current")

            status = director.jail.status(jail)

            output["services"].append({
                "name" : service,
                "status" : status,
                "jail" : jail
            })
    except Exception as err:
        _catch(log, err)

        sys.exit(EX_SOFTWARE)
    
    print(json.dumps(output, indent=2))

    sys.exit(EX_OK)

@cli.command(short_help="Check if a project exists")
@click.help_option()
@click.option("-p", "--project", help="Project name.")
def check(project):
    """
    Returns 0 if a project exists or non-zero if it does not exist.
    """

    if project is None:
        project = _get_project_name_from_env()

        if project is None:
            __project_name_not_specified()
            sys.exit(EX_DATAERR)

    log = director.log.Log(
        basedir=director.config.get("logs", "directory")
    )

    try:
        projectsdir = director.config.get("projects", "directory")

        project_obj = director.project.Project(project, basedir=projectsdir)

        if not os.path.isdir(project_obj.directory):
            sys.exit(EX_NOINPUT)
    except Exception as err:
        _catch(log, err)

        sys.exit(EX_SOFTWARE)

    sys.exit(EX_OK)

def __project_name_not_specified():
    print("The project name is not specified, use `--project` or", file=sys.stderr)
    print("set the `DIRECTOR_PROJECT` environment variable.", file=sys.stderr)

def _get_project_name_from_env(default=None):
    return os.getenv("DIRECTOR_PROJECT", default)

def _catch(log, err):
    with log.open("exception.log") as fd:
        print_err(err)

        print("", "file:", fd.name, file=sys.stderr)

        traceback.print_exc(file=fd)

def print_err(err):
        print("Exception:")
        print("", "type:", err.__class__.__name__, file=sys.stderr)
        print("", "error:", err, file=sys.stderr)

if __name__ == "__main__":
    cli()
