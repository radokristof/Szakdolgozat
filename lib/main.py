import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from colorama import Fore, Style, init  # type: ignore

from ansible_api.facts import gather_ios_facts
from ansible_api.playbook import run_playbook
from network_analyzer.NetworkAnalyzer import NetworkAnalyzer

logger = logging.getLogger()
LOGGER_LEVEL = logging.DEBUG


def setup_logging():
    """
    Setup logging for the project
    :return: None
    """
    default_formatter = logging.Formatter('[%(asctime)s] - %(name)s - %(levelness)s - %(message)s')
    logger.setLevel(LOGGER_LEVEL)
    # Add stdout handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(LOGGER_LEVEL)
    handler.setFormatter(default_formatter)
    logger.addHandler(handler)

    # Add file handler
    handler = logging.FileHandler("analyzer.log", 'w+')
    handler.setLevel(logging.INFO)
    handler.setFormatter(default_formatter)
    logger.addHandler(handler)

    # Set matplotlib logger to INFO only
    logging.getLogger('matplotlib').setLevel(logging.INFO)


def setup_parser():
    """
    Set CLI parser
    :return: The parsed arguments
    """
    parser = argparse.ArgumentParser(description="Szakdolgozat CLI tool")
    parser.add_argument('-p', '--playbook', metavar="playbook", type=str, help="Location of the playbook file to run")
    parser.add_argument('-s', '--source', type=str, dest="source", required=True, help="Source IP Address with netmask")
    parser.add_argument(
        '-d', '--destination', type=str, dest="destination", required=True, help="Destination IP Address with netmask"
    )
    parser.add_argument(
        '--data-dir', metavar="datadir", dest="datadir", type=str,
        default='../ansible/', help="Location of the private data dir"
    )
    parser.add_argument('--auto-fix', dest="autofix", action='store_true', help="Fix the detected errors")
    parser.add_argument('--no-auto-fix', dest="autofix", action="store_false", help="Just report detected errors")
    parser.add_argument(
        '--filename', dest="filename", default=f"plot_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.png",
        help="Filename of the plotted network (PNG)"
    )
    parser.set_defaults(autofix=True)
    return parser.parse_args()


def main():
    # Init colorama, setup logging
    init(autoreset=True)
    setup_logging()
    args = setup_parser()

    # Set Ansible cfg env variable
    os.environ["ANSIBLE_CONFIG"] = os.path.abspath("../ansible/ansible.cfg")

    # Change the permissions of the ansible/project/main.json file.
    # This is a remedy of ansible-runner (at least in Windows-WSL).
    # The file will be rewritten/recreated with wrong permissions,
    # so ansible-runner can't access it next time when running the program.
    os.chmod(os.path.abspath("../ansible/project/main.json"), 0o666)

    default_data_dir = os.path.abspath(args.datadir)

    logger.debug("Program initialization complete")
    print(Fore.CYAN + "Starting Network Analyzer Tool")
    print(Fore.GREEN + f"Source IP address/network: {args.source}")
    print(Fore.GREEN + f"Destination IP address/network: {args.destination}")
    logger.info("Running supplied playbook")

    # Run the selected playbook if there is a specified playbook
    # If the current network needs some pre-requisite setup,
    # you can specify that playbook which will be run before querying the network state
    # and making assumptions from the received state.
    if args.playbook:
        run_playbook(playbook_file=os.path.abspath(args.playbook), data_dir=default_data_dir)
        logger.debug("Supplied playbook finished")

    logger.debug("Running gather_facts playbook")
    # Run this playbook every time and get facts from this
    results = gather_ios_facts()

    # Run the network analyzer on the gathered facts
    analyzer = NetworkAnalyzer(
        results, source=args.source, destination=args.destination, test_case_name=Path(args.playbook).stem
    )
    network_state = analyzer.detect_loop_in_route()
    logger.debug(network_state)

    # Handle different network states here.
    # Loop: Try to eliminate if it is in the current route. Just warn if it is somewhere else.
    # Possible loop solutions: 
    #   Next hop is in the network, but the address has some typo
    #   The netmask is not correct (Longer netmask can cause real problems, first just warn for shorter netmask)
    result = False
    if network_state['loop'] is False and network_state['affected'] is False:
        logger.info("No problems found in network")
        print(Fore.GREEN + "There are no loops or ruptures in the network! Network seems healthy!")
        print(
            Fore.CYAN + f"Current route from {str(analyzer.source.network)} to "
                        f"{str(analyzer.destination.network)}: {', '.join(analyzer.get_shortest_path())}"
        )
    elif network_state['loop'] is False and network_state['affected'] is True:
        print(Fore.YELLOW + "There are no loops in the network, but there is a rupture. "
                            "If auto-repair is enabled, I will try to fix it!")
        logger.warning("Rupture found in network")
        if args.autofix:
            logger.debug("Auto-fixing rupture")
            print(Fore.RED + "Auto-fixing errors")
            result = analyzer.fix_rupture()
        else:
            logger.debug("No auto-fixing rupture")
            print(Fore.CYAN + "Summary status of the network can be seen in the generated graph")
    elif network_state['loop'] is True and network_state['affected'] is False:
        print(Fore.YELLOW + "There is a loop in the network, but it is not affecting the currently specified route!")
        print(Fore.MAGENTA + f"Current loop: {', '.join(network_state['members'])}")
    elif network_state['loop'] is True and network_state['affected'] is True:
        print(Fore.RED + "There is a loop in the network and the current route is affected!")
        print(Fore.MAGENTA + f"Current loop: {', '.join(network_state['members'])}")
        analyzer.fix_loop()

    # Plot the graph. If issues found, highlight the problematic node/edge and also indicate possible solutions as well.
    analyzer.plot_graph(filename=args.filename)

    if result:
        logger.info("Finished successfully")
        print(Fore.GREEN + "Problems fixed in network. It should be functional now!")
        print(
            Style.DIM + Fore.WHITE + "For additional information, "
                                     "what was fixed/replaced see the attached graph of the network or the logs!"
        )
    else:
        logger.error("Problems can't be fixed automatically")
        print(
            Fore.RED + "Problems cannot be fixed. Check them manually "
                       "or try running the program again with different source/destination parameters"
        )

    print(Fore.CYAN + "Program finished, exiting!")
    print(Fore.YELLOW + Style.DIM + "Bye!")


if __name__ == "__main__":
    main()
