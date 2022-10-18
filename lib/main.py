import os
import sys
import logging
import argparse
from ansible_api.playbook import run_playbook

logger = logging.getLogger(__name__)

def setup_logging():
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def main():
    setup_logging()
    
    # Ansible cfg env beállítása
    os.environ["ANSIBLE_CONFIG"] = os.path.abspath("../ansible/ansible.cfg")

    # CLI paraméterek beállítása
    parser = argparse.ArgumentParser(description="Szakdolgozat CLI tool")
    parser.add_argument('playbook', metavar="playbook", type=str, help="Location of the playbook file to run")
    parser.add_argument('--inventory', metavar="inv", dest='inventory', type=str, default='../ansible/hosts.yml', help="Location of the inventory file to use for the current run")
    parser.add_argument('--auto-fix', dest="autofix", action='store_true', help="Fix the detected errors")
    parser.add_argument('--no-auto-fix', dest="autofix", action="store_false", help="Just report detected errors")
    parser.set_defaults(autofix=True)
    args = parser.parse_args()
    
    logger.debug("Program initalization complete")
    logger.info("Running supplied playbook")
    run_playbook(inventory_file=os.path.abspath(args.inventory), playbook_file=os.path.abspath(args.playbook))
    logger.debug("Supplied playbook finished")

    logger.debug("Running gather_facts playbook")
    results = run_playbook(inventory_file=os.path.abspath(args.inventory), playbook_file=os.path.abspath('../ansible/gather-ios-facts.yml'))
    logger.debug("Facts gathered")

    print(results)

if __name__ == "__main__":
    main()
