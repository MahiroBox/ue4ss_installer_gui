import os
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime
from shutil import get_terminal_size


def get_is_log_file_use_disabled() -> bool:
    return "--disable_log_file_output" in sys.argv


def get_default_log_name_prefix() -> str:
    if "--log_name_prefix" in sys.argv:
        index = sys.argv.index("--log_name_prefix") + 1
        if index < len(sys.argv):
            return sys.argv[index]
    return f"{__name__.split('.')[0]}"


@dataclass
class LogInformation:
    log_base_dir: str
    log_prefix: str
    has_configured_logging: bool


log_information = LogInformation(
    log_base_dir=f"{os.getcwd()}/src",
    log_prefix=get_default_log_name_prefix(),
    has_configured_logging=False,
)


def set_log_base_dir(base_dir: str):
    log_information.log_base_dir = base_dir


def configure_logging(log_name_prefix: str = get_default_log_name_prefix()):
    log_information.log_prefix = log_name_prefix

    log_dir = os.path.join(log_information.log_base_dir)
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)

    rename_latest_log(log_dir)
    log_information.has_configured_logging = True


def rename_latest_log(log_dir):
    latest_log_path = os.path.join(log_dir, f"{log_information.log_prefix}_latest.log")
    if os.path.isfile(latest_log_path):
        try:
            timestamp = datetime.now().strftime("%m_%d_%Y_%H%M_%S")
            new_name = f"{log_information.log_prefix}_{timestamp}.log"
            new_log_path = os.path.join(log_dir, new_name)

            counter = 1
            while os.path.isfile(new_log_path):
                new_name = f"{log_information.log_prefix}_{timestamp}_({counter}).log"
                new_log_path = os.path.join(log_dir, new_name)
                counter += 1

            os.rename(latest_log_path, new_log_path)

        except PermissionError as e:
            log_message(f"Error renaming log file: {e}")
            return


def log_message(message: str):
    terminal_width = get_terminal_size().columns
    wrapped_lines = textwrap.wrap(message, width=terminal_width)

    for _, line in enumerate(wrapped_lines):
        print(line)

    if not log_information.has_configured_logging:
        return

    log_dir = os.path.join(log_information.log_base_dir)
    log_path = os.path.join(log_dir, f"{log_information.log_prefix}_latest.log")

    if not os.path.isdir(log_dir):
        if not get_is_log_file_use_disabled():
            os.makedirs(log_dir)

    if not os.path.isfile(log_path):
        try:
            if not get_is_log_file_use_disabled():
                with open(log_path, "w") as log_file:
                    log_file.write("")
        except OSError as e:
            print(f"Failed to create log file: {e}")
            return

    try:
        if not get_is_log_file_use_disabled():
            with open(log_path, "a") as log_file:
                log_file.write(f"{message}\n")
    except OSError as e:
        print(f"Failed to write to log file: {e}")
