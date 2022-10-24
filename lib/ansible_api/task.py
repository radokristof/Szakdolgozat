import logging
from pathlib import Path
import ansible_runner

logger = logging.getLogger(__name__)

def run_task(role, inventory_file):
    logger.debug("Running task/role with inventory {}".format(Path(inventory_file).name))
    r = ansible_runner.run(role=role)
    logger.info("{}: {}".format(r.status, r.rc))
    logger.debug(r.stats)
