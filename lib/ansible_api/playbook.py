import logging
from pathlib import Path
import ansible_runner  # type: ignore

from network_analyzer.exception.exception import PlaybookRunException

logger = logging.getLogger(__name__)


def run_playbook(playbook_file: str, data_dir: str) -> dict:
    """
    Run the given playbook via Ansible
    :param playbook_file: The playbook file path to run
    :param data_dir: The private_data_dir for ansible_runner.
        This is the directory where the playbook/inventory file is located
    :return: The facts gathered by the playbook
    """
    logger.info("Running playbook '{}' in data_dir '{}'".format(Path(playbook_file).name, Path(data_dir).name))
    r = ansible_runner.run(private_data_dir=data_dir, playbook=playbook_file)
    logger.info("{} ({})".format(r.status, r.rc))
    if r.status != "successful":
        raise PlaybookRunException(f"Playbook run failed {r.status}")
    logger.debug(r.stats)
    host_facts = {}
    for ok_host in r.stats['ok']:
        facts = r.get_fact_cache(ok_host)
        host_facts[ok_host] = facts
    return host_facts
