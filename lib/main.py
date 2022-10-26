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

def setup_parser():
    # Set CLI parser
    parser = argparse.ArgumentParser(description="Szakdolgozat CLI tool")
    parser.add_argument('playbook', metavar="playbook", type=str, help="Location of the playbook file to run")
    parser.add_argument('-s', type=str, dest="source", required=True, help="Source IP Address with netmask")
    parser.add_argument('-d', type=str, dest="destination", required=True, help="Destination IP Address with netmask")
    parser.add_argument('--data-dir', metavar="datadir", dest="datadir", type=str, default='../ansible/', help="Location of the private data dir")
    parser.add_argument('--auto-fix', dest="autofix", action='store_true', help="Fix the detected errors")
    parser.add_argument('--no-auto-fix', dest="autofix", action="store_false", help="Just report detected errors")
    parser.add_argument('--filename', dest="filename", default="plot.png", help="Filename of the plotted network (PNG)")
    parser.set_defaults(autofix=True)
    return parser.parse_args()

def main():
    # Init colorama, setup logging
    init(autoreset=True)
    setup_logging()
    args = setup_parser()

    # Set Ansible cfg env variable
    os.environ["ANSIBLE_CONFIG"] = os.path.abspath("../ansible/ansible.cfg")

    default_data_dir = os.path.abspath(args.datadir)
    
    logger.debug("Program initalization complete")
    print(Fore.CYAN + "Starting Network Analyzer Tool")
    print(Fore.GREEN + f"Source IP address/network: {args.source}")
    print(Fore.GREEN + f"Destination IP address/network: {args.destination}")
    logger.info("Running supplied playbook")
    
    # Run the selected playbook
    run_playbook(playbook_file=os.path.abspath(args.playbook), data_dir=default_data_dir)
    logger.debug("Supplied playbook finished")

    logger.debug("Running gather_facts playbook")
    # Run this playbook every time and get facts from this
    results = run_playbook(playbook_file=os.path.abspath('../ansible/project/gather-ios-facts.yml'), data_dir=default_data_dir)
    logger.debug("Facts gathered")

    # Run the network analyzer on the gathered facts
    analyzer = NetworkAnalyzer(results, source=args.source, destination=args.destination)
    network_state = analyzer.detect_loop_in_route()
    logger.debug(network_state)
    # Handle different network states here.
    # Loop: Try to eliminate if it is in the current route. Just warn if it is somewhere else.
    # Possible loop solutions: 
    #   Next hop is in the network, but the address has some typo
    #   The netmask is not correct (Longer netmask can cause real problems, first just warn for shorter netmask)
    
    # Plot the graph. If issues found, highlight the problematic node/edge and also indicate possible solutions as well.
    analyzer.plot_graph(filename=args.filename)
    
    # Fix the found errors if requested.
    if args.autofix:
        print(Fore.RED + "Auto-fixing errors")
        # run_task(role='cisco-config-interfaces', hosts="routers", vars={'interfaces': []}, data_dir=os.path.abspath('../ansible/'))
    else:
        print(Fore.CYAN + "Status of network")
        print("Print status")
    
    print(Fore.CYAN + "Program finished, exiting!")
    print(Fore.YELLOW + Style.DIM + "Bye!")
    
if __name__ == "__main__":
    main()
