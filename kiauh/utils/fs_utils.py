#!/usr/bin/env python3

# ======================================================================= #
#  Copyright (C) 2020 - 2024 Dominik Willner <th33xitus@gmail.com>        #
#                                                                         #
#  This file is part of KIAUH - Klipper Installation And Update Helper    #
#  https://github.com/dw-0/kiauh                                          #
#                                                                         #
#  This file may be distributed under the terms of the GNU GPLv3 license  #
# ======================================================================= #

import shutil
from pathlib import Path
from subprocess import DEVNULL, PIPE, CalledProcessError, check_output, run
from zipfile import ZipFile

from core.decorators import deprecated
from core.logger import Logger


def check_file_exist(file_path: Path, sudo=False) -> bool:
    """
    Helper function for checking the existence of a file |
    :param file_path: the absolute path of the file to check
    :param sudo: use sudo if required
    :return: True, if file exists, otherwise False
    """
    if sudo:
        try:
            command = ["sudo", "find", file_path.as_posix()]
            check_output(command, stderr=DEVNULL)
            return True
        except CalledProcessError:
            return False
    else:
        if file_path.exists():
            return True
        else:
            return False


def create_symlink(source: Path, target: Path, sudo=False) -> None:
    try:
        cmd = ["ln", "-sf", source.as_posix(), target.as_posix()]
        if sudo:
            cmd.insert(0, "sudo")
        run(cmd, stderr=PIPE, check=True)
    except CalledProcessError as e:
        Logger.print_error(f"Failed to create symlink: {e}")
        raise


def remove_with_sudo(file: Path) -> None:
    try:
        cmd = ["sudo", "rm", "-rf", file.as_posix()]
        run(cmd, stderr=PIPE, check=True)
    except CalledProcessError as e:
        Logger.print_error(f"Failed to remove file: {e}")
        raise


@deprecated(info="Use remove_with_sudo instead", replaced_by=remove_with_sudo)
def remove_file(file_path: Path, sudo=False) -> None:
    try:
        cmd = f"{'sudo ' if sudo else ''}rm -f {file_path}"
        run(cmd, stderr=PIPE, check=True, shell=True)
    except CalledProcessError as e:
        log = f"Cannot remove file {file_path}: {e.stderr.decode()}"
        Logger.print_error(log)
        raise


def run_remove_routines(file: Path) -> None:
    try:
        if not file.is_symlink() and not file.exists():
            Logger.print_info(f"File '{file}' does not exist. Skipped ...")
            return

        if file.is_dir():
            shutil.rmtree(file)
        elif file.is_file() or file.is_symlink():
            file.unlink()
        else:
            raise OSError(f"File '{file}' is neither a file nor a directory!")
        Logger.print_ok(f"File '{file}' was successfully removed!")
    except OSError as e:
        Logger.print_error(f"Unable to delete '{file}':\n{e}")
        try:
            Logger.print_info("Trying to remove with sudo ...")
            remove_with_sudo(file)
            Logger.print_ok(f"File '{file}' was successfully removed!")
        except CalledProcessError as e:
            Logger.print_error(f"Error deleting '{file}' with sudo:\n{e}")
            Logger.print_error("Remove this directory manually!")


def unzip(filepath: Path, target_dir: Path) -> None:
    """
    Helper function to unzip a zip-archive into a target directory |
    :param filepath: the path to the zip-file to unzip
    :param target_dir: the target directory to extract the files into
    :return: None
    """
    with ZipFile(filepath, "r") as _zip:
        _zip.extractall(target_dir)
