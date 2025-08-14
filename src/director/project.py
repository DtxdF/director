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
import os
import psutil
import re
import secrets
import shutil
import signal

import director.default
import director.exceptions
import director.keys
import director.parser

STATES = ("done", "failed", "unfinished", "destroying")
STATE_DONE = 0
STATE_FAILED = 1
STATE_UNFINISHED = 2
STATE_DESTROYING = 3

class Project(director.keys.Key):
    def __init__(self, name, file=None, basedir=".", locksdir=None):
        self.next_file = file

        self.name = name

        if not check_name(self.name):
            raise director.exceptions.InvalidProjectName(f"{self.name}: Invalid project name.")

        projectsdir = basedir
        self.directory = f"{projectsdir}/{name}"

        self.current_file = f"{self.directory}/{director.default.DIRECTOR_FILE}"
        self.current_spec = None

        self.next_spec = None

        self.new_project = None

        self.lock_keys = None

        if locksdir is not None:
            locksdir = f"{locksdir}/{name}"

            self.lock_keys = director.keys.Key(locksdir)

        super().__init__(self.directory)

    def __enter__(self):
        self.open()

        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def open(self):
        self.lock()

        try:
            self.parse_next_spec()
            self.parse_current_spec()

            if os.path.isfile(self.current_file):
                os.remove(self.current_file)

                self.new_project = False
            else:
                self.new_project = True

            dirname = os.path.dirname(self.current_file)

            if dirname != "":
                os.makedirs(dirname, exist_ok=True)

            shutil.copyfile(self.next_file, self.current_file)

            os.chmod(self.current_file, 0o440)
        except:
            # If an exception occurs, the lock file can be left when it is not convenient.
            self.unlock()
            raise

    def close(self):
        self.unlock()

    def set_state(self, state):
        self.set_key("state", STATES[state])

    def check_state(self, state):
        current_state = self.get_state()

        return STATES[state] == current_state

    def get_state(self):
        return self.get_key("state")

    def register_process(self):
        pid = self.get_pid()

        if pid is not None:
            try:
                os.kill(pid, 0)

                raise director.exceptions.ProcessAlreadyExists(f"{pid}: Can't create PID file because the process is already running.")
            except ProcessLookupError:
                pass

        ppid = os.getppid()
        pid = os.getpid()

        self.set_key("ppid", "%d" % ppid)
        self.set_key("pid", "%d" % pid)

    def get_pid(self):
        pid = self.get_key("pid")

        if pid is not None:
            return int(pid)

    def get_ppid(self):
        ppid = self.get_key("ppid")

        if ppid is not None:
            return int(ppid)

    def remove_process(self):
        self.unset_key("ppid")
        self.unset_key("pid")

    def terminate(self):
        if not self.check_state(STATE_UNFINISHED):
            return

        ppid = self.get_ppid()

        pid = self.get_pid()

        if ppid is None or pid is None:
            return

        proc_info = psutil.Process(pid)

        parent = proc_info.parent()

        if parent is None:
            raise director.exceptions.NoSuchProcess(f"{pid}: Unknown parent PID for this process.")

        if ppid != parent.pid:
            raise director.exceptions.AccessDenied(f"{ppid} != {parent.pid}: Known parent PID differs from " \
                    "the current parent PID.")

        os.kill(pid, signal.SIGTERM)

    def lock(self):
        if self.lock_keys is None:
            self.__raise_LocksNotFound()

        if self.locked():
            lockfile = self.lock_keys.get_keyfile("lock")

            raise director.exceptions.ProjectLocked(f"{self.name}: Project locked. Run `rm -f {lockfile}` " \
                    "if you are sure that no other process is locking this project.")

        self.lock_keys.set_key("lock", "")

    def locked(self):
        if self.lock_keys is None:
            self.__raise_LocksNotFound()

        return self.lock_keys.has_key("lock")

    def unlock(self):
        if self.lock_keys is None:
            self.__raise_LocksNotFound()

        self.lock_keys.unset_key("lock")

    def parse_next_spec(self):
        if self.next_spec is not None:
            return

        if self.next_file is None:
            raise director.exceptions.DirectorFileNotDefined("Director file not defined.")

        self.next_spec = director.parser.load(self.next_file)

    def parse_current_spec(self):
        if self.current_spec is not None:
            return

        if os.path.isfile(self.current_file):
            self.current_spec = director.parser.load(self.current_file)
        else:
            self.parse_next_spec()
            self.current_spec = copy.deepcopy(self.next_spec)

    def get_removed(self):
        self.parse_current_spec()
        self.parse_next_spec()

        current_services = set(self.current_spec["services"])
        next_services = set(self.next_spec["services"])

        return current_services - next_services

    def get_services(self, next=True):
        spec = self.__get_spec(next)

        return set(spec["services"])

    def has_failed(self, service):
        return self.has_key(f"{service}/fail")

    def set_fail(self, service):
        self.set_key(f"{service}/fail", "")

    def set_done(self, service):
        self.unset_key(f"{service}/fail")

    def get_jail_name(self, service_name, where="both", random_name=True, cached=True):
        if where != "next" and where != "current" and \
                where != "both":
            raise ValueError(f"{where}: Invalid option.")

        service = None

        if where == "both" or where == "next":
            services = self.__get_spec().get("services", {})
            service = services.get(service_name)
        
        if service is None and (where == "both" or where == "current"):
            services = self.__get_spec(False).get("services", {})
            service = services.get(service_name)

        if service is None:
            self.__raise_ServiceNotFound(service_name)

        if cached:
            jail = self.get_key(f"{service_name}/name", service.get("name"))
        else:
            jail = service.get("name")

        if jail is None:
            if not random_name:
                return None

            jail = generate_random_name()

        self.set_key(f"{service_name}/name", jail)

        return jail

    def differ(self, service):
        # This is a clear indication that we must recreate all services.
        if self.new_project is None or self.new_project:
            return True

        self.parse_current_spec()
        self.parse_next_spec()

        current_services = self.current_spec.get("services")
        next_services = self.next_spec.get("services")

        if current_services is None or next_services is None:
            return True

        current_service = self.current_spec["services"].get(service)
        next_service = self.next_spec["services"].get(service)

        if current_service is None or next_service is None:
            return True

        return current_service != next_service

    def differ_options(self):
        if self.new_project is None or self.new_project:
            return True

        self.parse_current_spec()
        self.parse_next_spec()

        current_options = self.current_spec.get("options")
        next_options = self.next_spec.get("options")

        if current_options is None and next_options is None:
            return False

        return current_options != next_options

    def get_default_volume_type(self, next=True):
        spec = self.__get_spec(next)

        return spec.get("default_volume_type")

    def get_priority(self, service, next=True):
        return self.__get_service(service, next).get("priority", director.default.PRIORITY)

    def reset_options(self, service, next=True):
        return self.__get_service(service, next).get("reset_options", director.default.RESET_OPTIONS)

    def ignore_mtime(self, service, next=True):
        return self.__get_service(service, next).get("ignore_mtime", director.default.IGNORE_MTIME)

    def get_options(self, next=True):
        spec = self.__get_spec(next)

        return spec.get("options", [])

    def get_local_options(self, service, next=True):
        return self.__get_service(service, next).get("options", [])

    def get_arguments(self, service, next=True):
        return self.__get_service(service, next).get("arguments", [])

    def get_environment(self, service, next=True):
        return self.__get_service(service, next).get("environment", [])

    def get_start_environment(self, service, next=True):
        return self.__get_service(service, next).get("start-environment", [])

    def get_oci(self, service, next=True):
        return self.__get_service(service, next).get("oci", {})

    def get_makejail(self, service, next=True):
        return self.__get_service(service, next).get("makejail", director.default.MAKEJAIL)

    def get_start_arguments(self, service, next=True):
        return self.__get_service(service, next).get("start", [])

    def get_scripts(self, service, next=True):
        return self.__get_service(service, next).get("scripts", [])

    def get_jail_volumes(self, service, next=True):
        return self.__get_service(service, next).get("volumes", [])

    def get_volumes(self, next=True):
        spec = self.__get_spec(next)

        return spec.get("volumes", {})

    def set_makejail_mtime(self, service):
        mtime = self.get_makejail_mtime(service)

        self.set_key(f"{service}/makejail_mtime", str(mtime))

    def check_makejail_mtime(self, service):
        key_mtime = self.get_current_makejail_mtime(service)
        file_mtime = self.get_makejail_mtime(service)

        return key_mtime < file_mtime

    def get_makejail_mtime(self, service):
        makejail = self.get_makejail(service)

        if os.path.isfile(makejail):
            mtime = os.path.getmtime(makejail)
        else:
            mtime = 0.0

        return mtime

    def get_current_makejail_mtime(self, service):
        return float(self.get_key(f"{service}/makejail_mtime", 0.0))

    def __get_service(self, name, next=True):
        spec = self.__get_spec(next)

        service = spec["services"].get(name)

        if service is None:
            self.__raise_ServiceNotFound(name)

        return service

    def __get_spec(self, next=True):
        if next:
            self.parse_next_spec()

            spec = self.next_spec
        else:
            self.parse_current_spec()

            spec = self.current_spec

        return spec

    def __raise_ServiceNotFound(self, name):
        raise director.exceptions.ServiceNotFound(f"{name}: Service not found.")

    def __raise_LocksNotFound(self):
        raise director.exceptions.LocksNotFound(f"{self.name}: Location of locks not configured.")

def check_name(name):
    return re.match(r"^[a-zA-Z0-9._-]+$", name) is not None

def generate_random_name():
    while True:
        name = secrets.token_hex(5)

        # Fix 'name cannot be numeric (unless it is the jid)'
        if not re.match(r"^\d+$", name):
            return name
