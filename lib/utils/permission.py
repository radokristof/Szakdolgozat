import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def change_ansible_runner_permissions() -> None:
    """
    Change the permissions of the ansible/project/main.json file.
    This is a remedy of ansible-runner (at least in Windows-WSL).
    The file will be rewritten/recreated with wrong permissions,
    so ansible-runner can't access it next time when running the program.
    """
    ansible_json_file_path = os.path.abspath("../ansible/project/main.json")
    runner_json_file = Path(ansible_json_file_path)
    if runner_json_file.exists():
        logger.debug("Changing permissions - {}".format(str(ansible_json_file_path)))
        os.chmod(ansible_json_file_path, 0o666)
