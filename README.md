# AppJail Director

AppJail Director is a tool for running multi-jail environments on AppJail using a simple YAML specification. A Director file is used to define how one or more jails that make up your application are configured. Once you have a Director file, you can create and start your application with a single command: `appjail-director up`.

## Quick Start

Using AppJail Director is a three-step process:

1. Define your app's environment with a `Makejail` so it can be reproduced anywhere.
2. Define the services that make up your app in `appjail-director.yml` so they can be run together in an isolated environment.
3. Lastly, run `appjail-director up` and Director will start and run your entire app.

A Director file looks like this:

```yaml
options:
  - virtualnet: ':<random> default'
  - nat:
services:
  web:
    makejail: Makejail
    options:
      - expose: 5000
    volumes:
      - appdata: /app/data
  mariadb:
    makejail: gh+AppJail-makejails/mariadb
    arguments:
      - mariadb_user: 'example-user'
      - mariadb_password: 'my_cool_secret'
      - mariadb_database: 'appdb'
      - mariadb_root_password: 'my-secret-pw'
volumes:
  appdata:
    device: ./appdata
```

## Installation

**Bleeding-edge version**:

```sh
pkg install -y py311-pipx
pipx install git+https://github.com/DtxdF/director.git
appjail-director --help
```

**Note**: Remember to add `~/.local/bin` to `PATH`.

**Stable version**:

```sh
pkg install -y py311-director
```

[AppJail](https://appjail.readthedocs.io/en/latest/install) must be installed before using Director.

### Note about non-root users

If you want to run Director with a non-root user, you must [configure AppJail to do so](https://appjail.readthedocs.io/en/latest/trusted-users/).

By default, `~/.director` is used as the base directory, so every file generated by Director will belong to you.

## Ephemeral concept

Director treats each jail as ephemeral. This does not mean that your jails will not persist after you stop them or restart your system, what it means is that Director assumes that it is safe to destroy the jails since you have clearly separated the data that should be persisted from the data considered ephemeral.

## Configuration file

Read more details in `appjail-director --help` about which configuration files are used and how they are loaded.

### logs

#### directory

**type**: String.

**default**: `~/.director/logs`.

**description**: Directory where the logs will be stored.

### projects

#### directory

**type**: String.

**default**: `~/.director/projects`.

**description**: Directory where the projects and its metadata will be stored.

### locks

#### directory

**type**: String.

**default**: `/tmp/director/locks`.

**description**: Location of lock files.

### jails

#### remove\_recursive

**type**: Boolean.

**default**: `false`.

**description**: Only valid for ZFS. Recursively removes the jail and its references. 

#### remove\_force

**type**: Boolean.

**default**: `true`.

**description**: Only valid for ZFS. Forcibly removes the jail dataset.

### commands

#### timeout

**type**: Integer.

**default**: `1800`.

**description**: Timeout to avoid hangings caused by some operations such as the execution of Makejail or some custom commands in your Director file.

## Environment

You can use environment variables within the Director file:

```yaml
options:
  - virtualnet: ':<random> default'
  - nat:
services:
  web:
    makejail: Makejail
    options:
      - expose: 5000
    volumes:
      - appdata: /app/data
  mariadb:
    makejail: gh+AppJail-makejails/mariadb
    arguments:
      - mariadb_user: !ENV '${DB_USER}'
      - mariadb_password: !ENV '${DB_PASS}'
      - mariadb_database: !ENV '${DB_NAME:appdb}'
      - mariadb_root_password: !ENV '${DB_ROOT_PASS}'
volumes:
  appdata:
    device: ./appdata
```

Instead of setting each environment variable from the command line, you can use a `.env` file:

**.env**:

```
DIRECTOR_PROJECT=myapp
DB_USER=example-user
DB_PASS=my_cool_secret
DB_NAME=appdb
DB_ROOT_PASS=my-secret-pw
```

## Specification

### options

**type**: Array of dictionaries. Each dictionary (key and value) is a string. The value can be left empty.

**description**: Options that will be used by all services.

### services (required)

**type**: Dictionary.

**description**: This dictionary contains the services to be created and started. Each key is the name of the service that must be valid with the following regular expression: `^[a-zA-Z0-9._-]+$`. The name of the service is not the same as the name of the jail.

#### priority

**type**: Integer.

**default**: `99`.

**description**: Once the Director file has been processed, the services will be sorted using this number. Lower integers have higher priority, so those services will be processed first.

#### name

**type**: String.

**description**: Jail name. If not specified, a random hexadecimal string will be used.

#### makejail

**type**: String.

**default**: `Makejail`

**description**: Makejail to be executed.

#### reset\_options

**type**: Boolean.

**description**: The global options will be added to the local options. These options only take into account the local options per service.

#### ignore\_mtime

**type**: Boolean.

**description**: Do not recreate the service when the Makejail modification time changes.

#### options

It has the same effect as the global `options`, but only for the services in which it appears.

#### arguments

**type**: Array of dictionaries. Each dictionary (key and value) is a string.

**description**: Arguments to pass to the Makejail to be executed.

#### environment

**type**: Array of dictionaries. Each dictionary (key and value) is a string. The value can be left empty.

**description**: Environment variables valid only in the `build` stage.

#### start-environment

**type**: Array of dictionaries. Each dictionary (key and value) is a string. The value can be left empty.

**description**: Environment variables valid only in the `start` stage.

#### oci

**type**: Dictionary.

**description**: Settings used by OCI-related commands.

##### user

**type**: String.

**description**: Execute the process specified by the OCI image as another user.

##### workdir

**type**: String.

**description**: Execute the process specified by the OCI image in this working directory.

##### environment

**type**: Array of dictionaries. Each dictionary (key and value) is a string. The value can be left empty.

**description**: Environment variables used by the process specified by the OCI image.

#### volumes

**type**: Array of dictionaries. Each dictionary (key and value) is a string.

**description**: The key of each dictionary is used to obtain the volume options specified by the global `volumes`.

#### scripts

**type**: Array of dictionaries.

**description**: Scripts that will be executed once the jail is created and started.

##### shell

**type**: String.

**default**: `/bin/sh -c`

**description**: Shell used to execute the script.

##### type

**type**: String.

**default**: `jexec`

**options**: `jexec`, `local` and `chroot`.

**description**: In which environment the script will be executed.

##### text (required)

**type**: String.

**description**: Script to be executed.

#### start

**type**: Array of dictionaries. Each dictionary (key and value) is a string.

**description**: Arguments to be passed to the `start` stage.

#### serial

**type**: Integer.

**default**: `0`.

**description**: Director detects changes to re-run the Makejail, this item forces the execution of the Makejail.

### default\_volume\_type

**type**: String.

**description**: Default volume type when `type` is not defined in `volumes/{volume}`.

### volumes

**type**: Dictionary.

**description**: Describe the volume options used by the services.

#### device

**type**: String.

**description**: Device to be mounted.

#### type

**type**: String.

**default**: `<pseudofs>`.

**description**: Type of the file system. When using `nullfs`, `<pseudofs>` or `<volumefs>`, `device` is treated as a directory and after getting the absolute path it will be used as the actual `device`.

See [AppJail#pseudofs](https://github.com/DtxdF/AppJail#pseudofs) for more details about the pseudo-filesystem.

#### options

**type**: String.

**default**: `rw`.

**description**: Mount point options associated with the file system.

#### dump

**type**: Integer.

**default**: `0`.

**description**: It is used for these file systems by the `dump(8)` command to determine which file systems need to be dumped.

#### pass

**type**: Integer.

**default**: `0`.

**description**: It is used by the `fsck(8)` and `quotacheck(8)` programs to determine the order in which file system and quota checks are done at reboot time.

#### umask

**type**: Integer.

**description**: Valid only for `nullfs`, `<pseudofs>` and `<volumefs>` file systems. When defined the umask is set before the creation of the directory (aka device) and is restored after the directory is created.

#### mode

**type**: Integer.

**description**: Valid only for `nullfs`, `<pseudofs>` and `<volumefs>` file systems. Change the access permissions of the directory (aka device) after its creation.

#### owner

**type**: Integer or String.

**description**: Valid only for `nullfs`, `<pseudofs>` and `<volumefs>` file systems. When defined the directory owner is set after the creation of the directory (aka device). Note that if you use a string instead of an integer, it will be resolved from your local user database.

#### group

It has the same effect as `owner`, but for the device group.

## Notes

* `GIT_ASKPASS` environment variable is set to `true` to avoid hangings caused by `git(1)`.

## Contributing

If you have found a bug, have an idea or need help, use the [issue tracker](https://github.com/DtxdF/director/issues/new). Of course, PRs are welcome.
