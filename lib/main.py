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
from utils.permission import change_ansible_runner_permissions

logger = logging.getLogger()


def setup_logging(log_level: str) -> None:
    """
    Setup logging for the project
    :return: None
    """
    default_formatter = logging.Formatter('[%(asctime)s] - %(name)s - %(levelname)s - %(message)s')
    logger.setLevel(log_level)
    # Add stdout handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(default_formatter)
    logger.addHandler(handler)

    # Add file handler
    handler = logging.FileHandler("analyzer.log", mode='a', encoding='utf-8', delay=False)
    handler.setLevel(logging.INFO)
    handler.setFormatter(default_formatter)
    logger.addHandler(handler)

    # Set matplotlib logger to INFO only
    logging.getLogger('matplotlib').setLevel(logging.INFO)


def setup_parser() -> argparse.Namespace:
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
        '-f', '--filename', dest="filename", default=f"plot_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.png",
        help="Filename of the plotted network (PNG)"
    )
    parser.add_argument(
        '-l', '--log-level', dest="loglevel",
        default="INFO", help="Logging level in CLI (check python.logging for more info)"
    )
    parser.set_defaults(autofix=True)
    return parser.parse_args()


def main() -> None:
    """
    Main function
    :return: None
    """
    # Init colorama, setup logging
    init(autoreset=True)
    args = setup_parser()
    setup_logging(args.loglevel)

    # Set Ansible cfg env variable
    os.environ["ANSIBLE_CONFIG"] = os.path.abspath("../ansible/ansible.cfg")

    # Change the permissions of the ansible/project/main.json file.
    change_ansible_runner_permissions()

    default_data_dir = os.path.abspath(args.datadir)

    logger.debug("Program initialization complete")
    print(Fore.CYAN + "Starting Network Analyzer Tool")
    print(Fore.GREEN + f"Source IP address/network: {args.source}")
    print(Fore.GREEN + f"Destination IP address/network: {args.destination}")

    # Run the selected playbook if there is a specified playbook
    # If the current network needs some pre-requisite setup,
    # you can specify that playbook which will be run before querying the network state
    # and making assumptions from the received state.
    if args.playbook:
        logger.info("Running supplied playbook")
        run_playbook(playbook_file=os.path.abspath(args.playbook), data_dir=default_data_dir)
        logger.debug("Supplied playbook finished")

    logger.debug("Running gather_facts playbook")
    # Run this playbook every time and get facts from this
    results = gather_ios_facts()

    test_case_name = Path(args.playbook).stem if args.playbook else "Network analyzation"
    # Run the network analyzer on the gathered facts
    analyzer = NetworkAnalyzer(
        results, source=args.source, destination=args.destination, test_case_name=test_case_name
    )
    network_state = analyzer.detect_loop_in_route()
    logger.debug(network_state)

    # Handle different network states here.
    # Loop: Try to eliminate if it is in the current route. Just warn if it is somewhere else.
    # Possible loop solutions: 
    #   Next hop is in the network, but the address has some typo
    #   The netmask is not correct (Longer netmask can cause real problems, first just warn for shorter netmask)
    problem_found = False
    problem_fixed = False
    if network_state['source']['loop'] is False and network_state['source']['affected'] is False \
            and network_state['destination']['loop'] is False and network_state['destination']['affected'] is False:
        logger.info("No problems found in network (source/destination side)")
        print(Fore.GREEN + "There are no loops or ruptures in the network in either direction! Network seems healthy!")
        print(
            Fore.CYAN + f"Current route from {str(analyzer.source.network)} to "
                        f"{str(analyzer.destination.network)}: {', '.join(analyzer.get_shortest_path())}"
        )
        problem_found = True
        problem_fixed = True
    elif (network_state['source']['loop'] is False and network_state['source']['affected'] is True) \
            or (network_state['destination']['loop'] is False and network_state['destination']['affected'] is True):
        print(Fore.YELLOW + "There are no loops in the network, but there is a rupture. "
                            "If auto-repair is enabled, I will try to fix it!")
        logger.warning("Rupture found in network")
        if args.autofix:
            logger.debug("Auto-fixing rupture")
            print(Fore.RED + "Auto-fixing rupture")
            problem_fixed = analyzer.fix_rupture()
        else:
            logger.debug("No auto-fixing rupture")
            print(Fore.CYAN + "Summary status of the network can be seen in the generated graph")
        problem_found = True
    elif (network_state['source']['loop'] is True and network_state['source']['affected'] is False) \
            or (network_state['destination']['loop'] is True and network_state['destination']['affected'] is False):
        print(Fore.YELLOW + "There is a loop in the network, but it is not affecting the currently specified route!")
        print(Fore.MAGENTA + f"Current loop: {', '.join(network_state['members'])}")
        if args.autofix:
            logger.debug("Auto-fixing non-affecting loop")
            print(Fore.YELLOW + "Auto-fixing loop")
            problem_fixed = analyzer.fix_loop()
        else:
            logger.debug("No auto-fixing non-affecting loop")
            print(Fore.CYAN + "Summary status of the network can be seen in the generated graph")
        problem_found = True
    elif (network_state['source']['loop'] is True and network_state['source']['affected'] is True) or \
            (network_state['destination']['loop'] is True and network_state['destination']['affected'] is True):
        logger.debug("Loop found in network")
        print(Fore.RED + "There is a loop in the network and the current route is affected! If auto-repair is enabled, "
                         "I will try to eliminate the loop!")
        if network_state['source']['loop'] is True:
            print(Fore.MAGENTA + f"Current loop: {', '.join(network_state['source']['members'])}")
        elif network_state['destination']['loop'] is True:
            print(Fore.MAGENTA + f"Current loop: {', '.join(network_state['destination']['members'])}")
        if args.autofix:
            logger.debug("Auto-fixing loop")
            print(Fore.YELLOW + "Auto-fixing loop")
            problem_fixed = analyzer.fix_loop()
        else:
            logger.debug("No auto-fixing loop")
            print(Fore.CYAN + "Summary status of the network can be seen in the generated graph")
        problem_found = True

    if problem_found:
        logger.info("Finished successfully")
        # Plot the graph. If issues found,
        # highlight the problematic node/edge and also indicate possible solutions as well.
        analyzer.plot_graph(filename=args.filename)
        print(Fore.GREEN + "Finished successfully")
        if problem_fixed:
            logger.info("Problems fixed in network")
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
    else:
        logger.warning("Problems cannot be determined by the program")
        print(Fore.RED + "Problems cannot be determined by the program. Check them manually!")
    print(Fore.CYAN + "Program finished, exiting!")
    print(Fore.YELLOW + Style.DIM + "Bye!")


if __name__ == "__main__":
    main()
