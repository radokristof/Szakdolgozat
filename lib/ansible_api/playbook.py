import logging
from pathlib import Path
import ansible_runner

logger = logging.getLogger(__name__)

def run_playbook(inventory_file, playbook_file):
    logger.debug("Running playbook {} with inventory {}".format(Path(playbook_file).name, Path(inventory_file).name))
    r = ansible_runner.run(playbook=playbook_file, inventory=inventory_file)
    logger.info("{}: {}".format(r.status, r.rc))
    logger.debug(r.stats)
    host_facts = {}
    for ok_host in r.stats['ok']:
        facts = r.get_fact_cache(ok_host)
        host_facts[ok_host] = facts
    return host_facts
