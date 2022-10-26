import logging
from pathlib import Path
import ansible_runner

logger = logging.getLogger(__name__)

def run_task(role, hosts, vars, data_dir):
    logger.info("Running task/role {} in data dir {}".format(Path(role).name, Path(data_dir).name))
    r = ansible_runner.run(private_data_dir=data_dir, role=role, hosts=hosts, role_vars=vars, gather_facts=False)
    logger.info("{}: {}".format(r.status, r.rc))
    logger.debug(r.stats)
