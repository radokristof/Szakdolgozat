import logging
from pathlib import Path
import ansible_runner

from network_analyzer.exception.exception import PlaybookRunException

logger = logging.getLogger(__name__)

def run_playbook(playbook_file, data_dir):
    logger.info("Running playbook '{}' in data_dir '{}'".format(Path(playbook_file).name, Path(data_dir).name))
    r = ansible_runner.run(private_data_dir=data_dir, playbook=playbook_file)
    logger.info("{}: {}".format(r.status, r.rc))
    if r.status != "successful":
        raise PlaybookRunException(f"Playbook run failed {r.status}")
    logger.debug(r.stats)
    host_facts = {}
    for ok_host in r.stats['ok']:
        facts = r.get_fact_cache(ok_host)
        host_facts[ok_host] = facts
    return host_facts
