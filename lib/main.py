import os
import sys
import logging
import argparse
from colorama import Fore, Style, init

from ansible_api.playbook import run_playbook
from ansible_api.task import run_task
from network_analyzer.NetworkAnalyzer import NetworkAnalyzer

logger = logging.getLogger()
LOGGER_LEVEL = logging.DEBUG

def setup_logging():
    logger.setLevel(LOGGER_LEVEL)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(LOGGER_LEVEL)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def main():
    init(autoreset=True)
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
    print(Fore.CYAN + "Starting Network Analyzer Tool")
    
    logger.info("Running supplied playbook")
    
    # A megadott teszteset playbook lefuttatása
    run_playbook(inventory_file=os.path.abspath(args.inventory), playbook_file=os.path.abspath(args.playbook))
    logger.debug("Supplied playbook finished")

    logger.debug("Running gather_facts playbook")
    # Összes elérhető infó kinyerés a routerek-ből, annak érdekében, hogy a hiba elemzése minél könnyebb legyen
    results = run_playbook(inventory_file=os.path.abspath(args.inventory), playbook_file=os.path.abspath('../ansible/gather-ios-facts.yml'))
    logger.debug("Facts gathered")

    # Algoritmus futtatása, hiba keresése
    analyzer = NetworkAnalyzer(results)
    analyzer.plot_graph()
    
    # Javítás elküldése (ha lehetséges és kérte a felhasználó)
    if args.autofix:
        run_task()
    else:
        print("Print status")
    
    print(Fore.CYAN + "Program finished, exiting!")
    print(Fore.YELLOW + Style.DIM + "Bye!")
    
if __name__ == "__main__":
    # main()
    run_task('cisco-config-interfaces', '../ansible/hosts.yml')
