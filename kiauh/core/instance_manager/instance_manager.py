# ======================================================================= #
#  Copyright (C) 2020 - 2024 Dominik Willner <th33xitus@gmail.com>        #
#                                                                         #
#  This file is part of KIAUH - Klipper Installation And Update Helper    #
#  https://github.com/dw-0/kiauh                                          #
#                                                                         #
#  This file may be distributed under the terms of the GNU GPLv3 license  #
# ======================================================================= #
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import List, Type, TypeVar

from core.constants import SYSTEMD
from core.instance_manager.base_instance import BaseInstance
from core.logger import Logger
from utils.sys_utils import cmd_sysctl_service

T = TypeVar("T", bound=BaseInstance, covariant=True)


# noinspection PyMethodMayBeStatic
class InstanceManager:
    def __init__(self, instance_type: Type[T]) -> None:
        self._instance_type = instance_type
        self._current_instance: Type[T] | None = None
        self._instance_suffix: str | None = None
        self._instance_service: str | None = None
        self._instance_service_full: str | None = None
        self._instance_service_path: str | None = None
        self._instances: List[T] = []

    @property
    def instance_type(self) -> Type[T]:
        return self._instance_type

    @instance_type.setter
    def instance_type(self, value: Type[T]):
        self._instance_type = value

    @property
    def current_instance(self) -> Type[T] | None:
        return self._current_instance

    @current_instance.setter
    def current_instance(self, value: Type[T] | None) -> None:
        self._current_instance = value
        if value is not None:
            self.instance_suffix = value.suffix
            self.instance_service = value.get_service_file_name()
            self.instance_service_path = value.get_service_file_path()

    @property
    def instance_suffix(self) -> str | None:
        return self._instance_suffix

    @instance_suffix.setter
    def instance_suffix(self, value: str | None):
        self._instance_suffix = value

    @property
    def instance_service(self) -> str | None:
        return self._instance_service

    @instance_service.setter
    def instance_service(self, value: str | None) -> None:
        self._instance_service = value

    @property
    def instance_service_full(self) -> str:
        return f"{self._instance_service}.service"

    @property
    def instance_service_path(self) -> str | None:
        return self._instance_service_path

    @instance_service_path.setter
    def instance_service_path(self, value: str | None) -> None:
        self._instance_service_path = value

    @property
    def instances(self) -> List[Type[T]]:
        return self.find_instances()

    @instances.setter
    def instances(self, value: List[T]) -> None:
        self._instances = value

    def create_instance(self) -> None:
        if self.current_instance is not None:
            try:
                self.current_instance.create()
            except (OSError, subprocess.CalledProcessError) as e:
                Logger.print_error(f"Creating instance failed: {e}")
                raise
        else:
            raise ValueError("current_instance cannot be None")

    def delete_instance(self) -> None:
        if self.current_instance is not None:
            try:
                self.current_instance.delete()
            except (OSError, subprocess.CalledProcessError) as e:
                Logger.print_error(f"Removing instance failed: {e}")
                raise
        else:
            raise ValueError("current_instance cannot be None")

    def enable_instance(self) -> None:
        try:
            cmd_sysctl_service(self.instance_service_full, "enable")
        except subprocess.CalledProcessError as e:
            Logger.print_error(f"Error enabling service {self.instance_service_full}:")
            Logger.print_error(f"{e}")

    def disable_instance(self) -> None:
        try:
            cmd_sysctl_service(self.instance_service_full, "disable")
        except subprocess.CalledProcessError as e:
            Logger.print_error(f"Error disabling {self.instance_service_full}:")
            Logger.print_error(f"{e}")

    def start_instance(self) -> None:
        try:
            cmd_sysctl_service(self.instance_service_full, "start")
        except subprocess.CalledProcessError as e:
            Logger.print_error(f"Error starting {self.instance_service_full}:")
            Logger.print_error(f"{e}")

    def restart_instance(self) -> None:
        try:
            cmd_sysctl_service(self.instance_service_full, "restart")
        except subprocess.CalledProcessError as e:
            Logger.print_error(f"Error restarting {self.instance_service_full}:")
            Logger.print_error(f"{e}")

    def start_all_instance(self) -> None:
        for instance in self.instances:
            self.current_instance = instance
            self.start_instance()

    def restart_all_instance(self) -> None:
        for instance in self.instances:
            self.current_instance = instance
            self.restart_instance()

    def stop_instance(self) -> None:
        try:
            cmd_sysctl_service(self.instance_service_full, "stop")
        except subprocess.CalledProcessError as e:
            Logger.print_error(f"Error stopping {self.instance_service_full}:")
            Logger.print_error(f"{e}")
            raise

    def stop_all_instance(self) -> None:
        for instance in self.instances:
            self.current_instance = instance
            self.stop_instance()

    def find_instances(self) -> List[Type[T]]:
        from utils.common import convert_camelcase_to_kebabcase

        name = convert_camelcase_to_kebabcase(self.instance_type.__name__)
        pattern = re.compile(f"^{name}(-[0-9a-zA-Z]+)?.service$")
        excluded = self.instance_type.blacklist()

        service_list = [
            Path(SYSTEMD, service)
            for service in SYSTEMD.iterdir()
            if pattern.search(service.name)
            and not any(s in service.name for s in excluded)
        ]

        instance_list = [
            self.instance_type(suffix=self._get_instance_suffix(name, service))
            for service in service_list
        ]

        return sorted(instance_list, key=lambda x: self._sort_instance_list(x.suffix))

    def _get_instance_suffix(self, name: str, file_path: Path) -> str:
        # to get the suffix of the instance, we remove the name of the instance from
        # the file name, if the remaining part an empty string we return it
        # otherwise there is and hyphen left, and we return the part after the hyphen
        suffix = file_path.stem[len(name) :]
        return suffix[1:] if suffix else ""

    def _sort_instance_list(self, suffix: int | str | None):
        if suffix is None:
            return
        elif isinstance(suffix, str) and suffix.isdigit():
            return f"{int(suffix):04}"
        else:
            return suffix
