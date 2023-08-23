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

```sh
pkg install -y py39-pipx
pipx install git+https://github.com/DtxdF/director.git
appjail-director --help
```

**Note**: Remember to add `~/.local/bin` to `PATH`.

[AppJail](https://github.com/DtxdF/AppJail) must be installed before using Director.

### Note about non-root users

If you want to run Director with a non-root user, you must [configure AppJail to do so](https://github.com/DtxdF/AppJail#unprivileged-users).

You must also make sure that the project directory and the directory where the logs are stored have the correct permissions for your user. Note that when running a project with two different users will not work correctly, Director is meant to be run as the root user.

## Configuration file

AppJail Director has a very simple configuration file (`PREFIX/etc/director.ini`) which is an ini file. If such a file does not exist, the defaults will be used.

### logs

#### directory

**type**: String.

**default**: `PREFIX/director/logs`.

**description**: Directory where the logs will be stored.

### projects

#### directory

**type**: String.

**default**: `PREFIX/director/projects`.

**description**: Directory where the projects and its metadata will be stored.

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

#### options

It has the same effect as the global `options`, but only for the services in which it appears.

#### arguments

**type**: Array of dictionaries. Each dictionary (key and value) is a string.

**description**: Arguments to pass to the Makejail to be executed.

#### environment

**type**: Array of dictionaries. Each dictionary (key and value) is a string. The value can be left empty.

**description**: Environment variables valid only in the `build` stage.

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

### volumes

**type**: Dictionary.

**description**: Describe the volume options used by the services.

#### device

**type**: String.

**description**: Device to be mounted.

#### type

**type**: String.

**default**: `nullfs`.

**description**: Type of the file system. When using `nullfs`, `device` is treated as a directory and after getting the absolute path it will be used as the actual `device`.

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

## Contributing

If you have found a bug, have an idea or need help, use the [issue tracker](https://github.com/DtxdF/director/issues/new). Of course, PRs are welcome.
