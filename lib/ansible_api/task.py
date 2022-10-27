import logging
from pathlib import Path
import ansible_runner  # type: ignore

logger = logging.getLogger(__name__)


def run_task(role: str, hosts: str, role_vars: dict, data_dir: str) -> None:
    """
    Run the given task(s) via Ansible
    :param role: The role file to execute
    :param hosts: On which hosts to execute the role
    :param role_vars: Variables which will be passed to the role
    :param data_dir: The private_data_dir for ansible_runner.
    :return: None
    """
    logger.info("Running task/role {} in data dir {}".format(Path(role).name, Path(data_dir).name))
    r = ansible_runner.run(private_data_dir=data_dir, role=role, hosts=hosts, role_vars=role_vars)
    logger.info("{}: {}".format(r.status, r.rc))
    logger.debug(r.stats)
