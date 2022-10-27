import os
import logging

from ansible_api.playbook import run_playbook

logger = logging.getLogger(__name__)


def gather_ios_facts() -> dict:
    """
    Gather facts from Cisco IOS devices
    :return: The gathered facts
    """
    results = run_playbook(
        playbook_file=os.path.abspath('../ansible/project/gather-ios-facts.yml'), data_dir='../ansible'
    )
    logger.debug("Facts gathered")
    logger.debug(results)
    return results
