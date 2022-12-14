import logging
import os
from datetime import datetime
from typing import Tuple, Union, List

import matplotlib.pyplot as plt  # type: ignore
import netaddr  # type: ignore
import networkx as nx  # type: ignore

from ansible_api.facts import gather_ios_facts
from ansible_api.task import run_task
from network_analyzer.Host import Host, SourceHost, DestinationHost
from network_analyzer.exception.exception import NodeNotFoundException, NetworkSourceDestinationException, \
    NetworkMultipleDefinitionException
from utils.graph import get_interface_status_from_route, check_interface_status, check_source_destination, \
    check_loop_type, generate_tmp_graph, check_missing_interface_route, get_interface_ip_within_ip_network, \
    get_interface_status_from_ip, get_ip_address_from_same_subnet, get_route_match_by_dest
from utils.ip import compare_cidr_and_ip_address, check_network_contains_network

logger = logging.getLogger(__name__)

MANAGEMENT_NETWORK = netaddr.IPNetwork('10.10.20.0/24')


class NetworkAnalyzer:
    hosts = []
    graph_from_source = nx.DiGraph()
    graph_from_destination = nx.DiGraph()
    source = None
    destination = None

    errors = []

    def __init__(self, facts: dict, source: str, destination: str, test_case_name: str):
        """
        Create a new host for every fact element
        Add the hosts to the hosts directive
        :param facts: The gathered facts from Ansible
        :param source: The source network
        :param destination: The destination network
        :param test_case_name: Name of the test case (usually filename)
        """
        self.test_case = test_case_name
        for hostname, host_facts in facts.items():
            logger.debug(f"Adding host {hostname}")
            self.hosts.append(Host(host_facts))
        logger.debug("Hosts loaded")
        # Load source and destination network as netaddr
        try:
            source = netaddr.IPNetwork(source)
            destination = netaddr.IPNetwork(destination)
        except ValueError as e:
            logger.error("Source or destination network not correct {}".format(str(e)))

        self.init_network(source, destination)
        self.init_graph()

        # Create a copy of the initial graph.
        # This will not be changed and can be compared against when the fixes applied.
        self.initial_graph_from_source = self.graph_from_source
        self.initial_graph_from_destination = self.graph_from_destination

    def _refresh(self, facts: dict) -> None:
        """
        Refresh the current instance.
        Instead of calling __init__ directly (which is a bad practice), 
        use this method to re-initialize the instance.
        :param: facts: The fresh gathered facts from Ansible
        """
        self.hosts = []
        self.graph_from_source = nx.DiGraph()
        self.graph_from_destination = nx.DiGraph()
        for hostname, host_facts in facts.items():
            logger.debug(f"Adding host {hostname}")
            self.hosts.append(Host(host_facts))
        logger.debug("Hosts loaded")
        self.init_network(self.source.network, self.destination.network)
        self.init_graph()

    def init_graph(self) -> None:
        """
        Create an initial graph of the network
        Go through the network hosts
        :return: None
        """
        edges_from_source = []
        edges_from_destination = []
        for host in self.hosts:
            # Get all routes of a host
            for table in host.routes:
                if 'vrf' not in table:
                    source, destination = self.create_route_edge(host, table)
                    edges_from_source += source
                    edges_from_destination += destination
            for interface in host.interfaces:
                edge = self.create_pc_edge(host, interface)
                if edge:
                    edges_from_source.append(edge)
                    edges_from_destination.append(tuple(reversed(edge)))
        for source, destination in edges_from_source:
            self.graph_from_source.add_edge(source, destination, color='blue', weight=2, style='-',
                                            label='Route from source to destination')
        for source, destination in edges_from_destination:
            self.graph_from_destination.add_edge(source, destination, color='orange', weight=2, style='-',
                                                 label='Route from destination to source')
        logger.debug("Network initialization complete")

    def init_network(self, source: netaddr.IPNetwork, destination: netaddr.IPNetwork) -> None:
        """
        Initialize network, find source and destination network provided by the user.
        If these networks cannot be found in the current hosts, the program will exit
        :param source: The source network
        :param destination: The destination network
        :return: None
        :raises: NetworkSourceDestinationException if the source or destination network cannot be found
        """
        source_found = False
        destination_found = False
        for host in self.hosts:
            for interface in host.interfaces:
                net = check_source_destination(interface, source, destination)
                if net == "source" and source_found:
                    raise NetworkMultipleDefinitionException(
                        f"The network {str(destination)} is defined multiple times in the network")
                elif net == "source":
                    self.source = SourceHost(source, host.facts)
                    source_found = True
                elif net == "destination" and destination_found:
                    raise NetworkMultipleDefinitionException(
                        f"The network {str(destination)} is defined multiple times in the network")
                elif net == "destination":
                    self.destination = DestinationHost(destination, host.facts)
                    destination_found = True
        if source_found and destination_found:
            logger.info("Source and destination network found!")
        else:
            raise NetworkSourceDestinationException("Network source or destination not found in the network!")

    def create_graph_edge(self, host: Host, source_ip: str, forward: bool) -> Union[Tuple[str, str], None]:
        """
        Create a graph edge with source ip (IP address of current host)
        and finding the opposite side of the link in one of the available hosts
        :param host: The Host object
        :param source_ip: The IP address of the current route
        :param forward: Forward or backward route. If forward the tuple will be in the form (source, destination)
        :return: tuple with graph edges
        """
        try:
            dest_host = self.find_host_with_ip_address(source_ip)
        except NodeNotFoundException as e:
            logger.warning(e)
            return None
        else:
            # Return edge tuple based on direction
            return (host.hostname, dest_host.hostname) if forward is True else (dest_host.hostname, host.hostname)

    def create_route_edge(self, host: Host, table: dict) \
            -> Tuple[Union[List[Tuple[str, str]], List], Union[List[Tuple[str, str]], List]]:
        """
        Create a graph edge for a route
        :param host: The Host object
        :param table: The route table
        :return: tuple with graph edges (edges from source, edges from destination)
        """
        # Filter VRF routes. In our environment, VRF routes only represent management network access
        # which we would like to filter from our real network.
        edges_from_source = []
        edges_from_destination = []
        for route in table['address_families']:
            # Filter routes based on destination.
            # If the current route is not destined towards our destination network, ignore it.
            forward_router_address = route['routes'][0]['next_hops'][0]['forward_router_address']
            dest = netaddr.IPNetwork(route['routes'][0]['dest'])
            # Check destination network netmask!
            # Source or destination network should be contained by current routes destination network
            # If it is not contained, ignore this route.
            if check_network_contains_network(self.destination.network, dest) \
                    or check_network_contains_network(self.source.network, dest):
                # Need to check if the current route next-hop interface is enabled.
                # Also need to check if the current route interface is enabled on the other router as well.
                # If not enabled or netmask is smaller don't add the route
                # ! Routes returned by Ansible is always there, even if the actual routing table does not contain it !
                if get_interface_status_from_route(host, forward_router_address) and \
                        get_interface_status_from_ip(self.hosts, forward_router_address):
                    if check_network_contains_network(self.destination.network, dest):
                        edges_from_source.append(self.create_graph_edge(host, forward_router_address, forward=True))
                        logger.debug(f"Adding forward edge {edges_from_source[-1]} for host {host.hostname}")
                    if check_network_contains_network(self.source.network, dest):
                        edges_from_destination.append(
                            self.create_graph_edge(host, forward_router_address, forward=True)
                        )
                        logger.debug(f"Adding reverse edge {edges_from_destination[-1]} for host {host.hostname}")
        logger.debug(f"Edges for host {host.hostname}: {edges_from_source} {edges_from_destination}")
        return edges_from_source, edges_from_destination

    def create_pc_edge(self, host: Host, interface: dict) -> Union[Tuple[str, str], None]:
        """
        Create static PC nodes in the graph. These represent the computers used in network troubleshooting.
        PC-S will be the Source PC (this will be placed at the source network)
        PC-D will be the Destination PC (this will be placed at the destination network)
        :param host: The Host object which is a router next to the PC
        :param interface: The interface of the router which might be connected to the PC
        :return: tuple with an edge (router hostname, PC hostname)
        """
        if 'ipv4' in interface:
            if netaddr.IPNetwork(interface['ipv4'][0]['address']) == self.source.network:
                return 'PC-S', host.hostname
            elif netaddr.IPNetwork(interface['ipv4'][0]['address']) == self.destination.network:
                return host.hostname, 'PC-D'
        return None

    def detect_loop_in_route(self) -> dict:
        """
        Detect a loop in the routes.
        :return: Return a dictionary of loops in the source->destination and destination->source route
        """
        # Check if the current graph contains a loop.
        loops = {}
        source_loop = None
        destination_loop = None
        for loop in nx.simple_cycles(self.graph_from_source):
            source_loop = loop.copy()
        for loop in nx.simple_cycles(self.graph_from_destination):
            destination_loop = loop.copy()
        # The source_loop or destination_loop var is empty if there are no loops in the network
        loops['source'] = check_loop_type(
            graph=self.graph_from_source, loop=source_loop,
            source=self.source.hostname, destination=self.destination.hostname
        )
        loops['destination'] = check_loop_type(
            graph=self.graph_from_destination, loop=destination_loop,
            source=self.destination.hostname, destination=self.source.hostname
        )
        return loops

    def find_host_with_ip_address(self, ip_address: str) -> Host:
        """
        Check if a host has an IP Address
        Parameter ip_address is a normal ip address with dot notation. Like: 192.168.10.1
        Interface IP address is in CIDR notation. Like: 192.168.10.1/30
        Returns NodeNotFoundException if the IP address is not found in any of the hosts
        :param ip_address: The IP address to search for
        :return: The Host object
        """
        for host in self.hosts:
            for interface in host.interfaces:
                # If an interface does not have an IP address, it will not have an 'ipv4' key
                if 'ipv4' in interface:
                    # Check if the current IP address (network) is the same as the received ip_address.
                    if compare_cidr_and_ip_address(interface['ipv4'][0]['address'], ip_address):
                        return host
        # Raise error if the current IP address cannot be found in the network.
        raise NodeNotFoundException(f"Not found {ip_address}")

    def plot_graph(self, filename: str) -> None:
        """
        Plot the graph to a file
        Used for debugging and creating visualizations for thesis.
        Removed node: should be red
        Added node: should be dotted and green
        Warning node: should be yellow (edges which might have a problem but does not affect current routing)
        :param filename: Filename of the plot to be saved
        :return: None
        """
        logger.debug("Create plot of graph")
        # Get source graph new and removed edges
        source_tmp_graph = generate_tmp_graph("source", self.graph_from_source, self.initial_graph_from_source)

        # Get destination graph new and removed edges
        destination_tmp_graph = generate_tmp_graph("destination", self.graph_from_destination,
                                                   self.initial_graph_from_destination)

        # Combine the two graph into a single graph
        tmp_graph = nx.compose(source_tmp_graph, destination_tmp_graph)
        logger.debug(f"Temporary graph edges: {tmp_graph.edges(data=True)}")

        # Get the attributes of the nodes
        colors = nx.get_edge_attributes(tmp_graph, 'color').values()
        weights = nx.get_edge_attributes(tmp_graph, 'weight').values()
        styles = nx.get_edge_attributes(tmp_graph, 'style').values()

        logger.debug(f"Colors: {colors}")
        logger.debug(f"Weights: {weights}")
        logger.debug(f"Styles: {styles}")

        node_color = {
            'PC-S': 'tab:green',
            'PC-D': 'tab:red',
        }

        node_colors = [node_color.get(node, 'tab:blue') for node in tmp_graph.nodes()]

        node_size = {
            'PC-S': 1000,
            'PC-D': 1000,
        }
        node_sizes = [node_size.get(node, 800) for node in tmp_graph.nodes()]

        # Add title to plot
        plt.figure(3, figsize=(6, 6))
        plt.suptitle(f"Summary of {self.test_case}")
        plt.title(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        pos = nx.circular_layout(tmp_graph, scale=1)
        nx.draw_networkx_nodes(
            tmp_graph, pos=pos, node_color=node_colors, node_size=node_sizes, alpha=1
        )
        nx.draw_networkx_edges(
            tmp_graph, pos=pos, edge_color=colors, width=list(weights), style=list(styles),
            arrowsize=20, connectionstyle='arc3, rad = 0.1'
        )
        nx.draw_networkx_labels(tmp_graph, pos=pos, font_size=10, font_color='whitesmoke')

        # Show the graph
        plt.savefig(filename)
        logger.info(f"Plot saved to file {filename}!")

    def get_shortest_path(self) -> list:
        """
        Get the shortest path in a graph.
        :return: List of nodes in the shortest path
        """
        return nx.shortest_path(self.graph_from_source, self.source.hostname, self.destination.hostname)

    def refresh_network(self) -> None:
        """
        Gather facts and reinitialize network
        :return: None
        """
        results = gather_ios_facts()
        self._refresh(results)

    def check_fix(self) -> bool:
        """
        Check the applied fix. It returns True if the fix is applied correctly.
        :return: True if the network is fixed, False otherwise.
        """
        self.refresh_network()
        network_state = self.detect_loop_in_route()
        if network_state['source']['affected'] is False and network_state['destination']['affected'] is False:
            return True
        return False

    def fix_rupture(self) -> bool:
        """
        Fix ruptures in the network
        This function will detect multiple types of ruptures.
        First it will scan for disabled interfaces in the source->destination and destination->source direction.
        If this fix is not enough (the network still has ruptures) it will try to find missing routes in the network.
        :return: True if the network is fixed, False otherwise.
        """
        logger.debug("Init fixing rupture")
        # Check if configured interfaces are up
        # Collect down interfaces (which has in IP address configured)
        all_down_interfaces = {}
        for host in self.hosts:
            down_interfaces = check_interface_status(host, self.source.network, self.destination.network)
            if down_interfaces:
                all_down_interfaces[host.hostname] = down_interfaces
        logger.debug(f"Down interfaces: {all_down_interfaces}")
        # Enable all filtered down interface
        enabled_at_least_one_interface = False
        for hostname, down_interfaces in all_down_interfaces.items():
            logger.debug(f"Enabling interfaces {down_interfaces} on host {hostname}")
            run_task(
                role='cisco-config-interfaces', hosts=hostname,
                role_vars={'interfaces': down_interfaces}, data_dir=os.path.abspath('../ansible/')
            )
            enabled_at_least_one_interface = True
        if enabled_at_least_one_interface:
            logger.debug("Enabled at least one interface")
            # Check if the enabling helped to solve the rupture.
            # We need to gather ios facts again and recreate the NetworkAnalyzer instance.
            fixed = self.check_fix()
            if fixed:
                logger.info("Interfaces enabled - network fixed")
                return True
        logger.info("Continuing with fixes - enabling interfaces was not enough")
        missing_routes = {}
        # Check if there are missing routes
        # Forward route
        rupture_node_source = self.traverse_route(self.graph_from_source, self.source.hostname, 'PC-D')
        reverse_rupture_node_source = self.traverse_route(self.graph_from_source.reverse(copy=True),
                                                          self.destination.hostname, 'PC-S')
        missing_routes['source'] = (rupture_node_source, reverse_rupture_node_source)
        logger.debug(f"Rupture in forward route: Between {rupture_node_source} and {reverse_rupture_node_source}")

        # Reverse route
        rupture_node_destination = self.traverse_route(self.graph_from_destination, self.destination.hostname, 'PC-S')
        reverse_rupture_node_destination = self.traverse_route(self.graph_from_destination.reverse(copy=True),
                                                               self.source.hostname, 'PC-D')
        missing_routes['destination'] = (rupture_node_destination, reverse_rupture_node_destination)
        logger.debug(
            f"Rupture in reverse route: Between {rupture_node_destination} and {reverse_rupture_node_destination}"
        )
        fixed_route = False
        logger.debug(f"Missing routes: {missing_routes}")
        for direction, edges in missing_routes.items():
            if None not in edges:
                logger.debug(f"Missing route in {direction} between {edges}")
                source_host = self.get_host_from_hostname(edges[0])
                destination_host = self.get_host_from_hostname(edges[1])
                source_ips_without_route, routes_with_incorrect_netmask = check_missing_interface_route(
                    source_host, self.source.network, self.destination.network
                )
                logger.debug(f"Source missing routes: {source_ips_without_route}")
                logger.debug(f"Routes with incorrect netmask: {routes_with_incorrect_netmask}")

                next_hop_addr = get_interface_ip_within_ip_network(destination_host,
                                                                   source_ips_without_route)
                replaced_routes = []
                for route, next_hop in routes_with_incorrect_netmask:
                    # Need to deleted wrong routes
                    # And new ones needs to be added (as the network mask differs)
                    if check_network_contains_network(route, self.source.network):
                        logger.debug(
                            f"Changing source network mask for route {route} to /{self.source.network.prefixlen}"
                        )
                        replaced_routes.append({
                            'state': 'deleted',
                            'dest_address': route,
                            'next_hop': next_hop
                        })
                        replaced_routes.append({
                            'state': 'merged',
                            'dest_address': str(self.source.network.cidr),
                            'next_hop': next_hop
                        })
                    elif check_network_contains_network(route, self.destination.network):
                        logger.debug(
                            f"Changing destination network mask "
                            f"for route {route} to /{self.destination.network.prefixlen}"
                        )
                        replaced_routes.append({
                            'state': 'deleted',
                            'dest_address': route,
                            'next_hop': next_hop
                        })
                        replaced_routes.append({
                            'state': 'merged',
                            'dest_address': str(self.destination.network.cidr),
                            'next_hop': next_hop
                        })
                logger.debug(f"Replaced routes: {replaced_routes}")
                if replaced_routes:
                    logger.info("Replacing routes with incorrect netmask")
                    run_task(
                        role='cisco-config-static_routes', hosts=source_host.hostname,
                        role_vars={'routes': replaced_routes},
                        data_dir=os.path.abspath('../ansible/')
                    )
                    fixed_route = True
                if next_hop_addr:
                    logger.debug(f"Destination missing routes: {next_hop_addr}")
                    run_task(
                        role='cisco-config-static_routes', hosts=source_host.hostname,
                        role_vars={'routes': [
                            {
                                'dest_address': str(
                                    self.destination.network.cidr if direction == 'source'
                                    else self.source.network.cidr),
                                'next_hop': str(netaddr.IPNetwork(next_hop_addr).ip)
                            }
                        ]},
                        data_dir=os.path.abspath('../ansible/')
                    )
                    fixed_route = True
                else:
                    logger.debug("No next hop address found. Cannot be fixed!")
        if fixed_route:
            fixed = self.check_fix()
            if fixed:
                logger.info("Missing route fixed")
                return True
        return False

    def get_host_from_hostname(self, hostname: str) -> Host:
        """
        Get a Host object from unique hostname
        :param hostname: The hostname of the host
        :return: The Host object
        """
        for host in self.hosts:
            if host.hostname == hostname:
                return host

    def traverse_route(self, graph: nx.DiGraph, source_node: str, dest_node: str) -> Union[str, None]:
        """
        Traverse the graph from source to destination node and find the last node in the route.
        If the destination node is found, None will be returned.
        Otherwise, the last node name will be returned
        :param graph: The graph to traverse
        :param source_node: The source where the traverse should be started
        :param dest_node: The destination which should be reached
        :return: Last node or None
        """
        logger.debug(f"Traversing {source_node}")
        neighbor = [n for n in graph.neighbors(source_node)]
        if not neighbor:
            logger.debug("Last node with neighbor found!")
            return source_node
        if neighbor[0] == dest_node:
            logger.debug(f"Found destination ({neighbor[0]}), no route missing!")
            return None
        return self.traverse_route(graph, neighbor[0], dest_node)

    def check_and_fix_loop(self, last_node_in_loop: str, last_node_from_dest: str,
                           destination_network: Union[netaddr.IPNetwork, str]) -> bool:
        """
        Helper function to check a node if it is where the loop is sourced from.
        Fix the route if this is the correct node, return False if it is not the right node
        :param last_node_in_loop: The last node in the loop
        :param last_node_from_dest: The last node from the destination
        :param destination_network: The destination network which needs to be reached.
        :return: True if the route was fixed with this node, False if not, needs to check other nodes
        """
        logger.debug(f"Last node in loop: {last_node_in_loop}")
        common_ips = get_ip_address_from_same_subnet(
            self.get_host_from_hostname(last_node_in_loop),
            self.get_host_from_hostname(last_node_from_dest)
        )
        logger.debug(f"Common IPs: {common_ips}")
        possible_ip = tuple()
        for source, dest in common_ips:
            if not check_network_contains_network(source, MANAGEMENT_NETWORK) and \
                    not check_network_contains_network(dest, MANAGEMENT_NETWORK):
                logger.info(f"Found possible fix: {source} -> {dest}")
                possible_ip = (source, dest)
                break
        if possible_ip:
            # Get route which is towards destination network (or contained in it)
            # Rewrite that rule (without changing the destination) with its new next_hop ip
            original_dest, wrong_next_hop = get_route_match_by_dest(
                self.get_host_from_hostname(last_node_in_loop),
                destination_network
            )
            logger.debug(f"Removing route from {last_node_in_loop} - {wrong_next_hop} towards {original_dest}")
            run_task(
                role='cisco-config-static_routes', hosts=last_node_in_loop,
                role_vars={'routes': [
                    {
                        'dest_address': str(original_dest),
                        'next_hop': str(wrong_next_hop),
                        'state': 'deleted'
                    }
                ]},
                data_dir=os.path.abspath('../ansible/')
            )
            logger.debug(f"Adding route to {last_node_in_loop} - {possible_ip[1]} towards {original_dest}")
            run_task(
                role='cisco-config-static_routes', hosts=last_node_in_loop,
                role_vars={'routes': [
                    {
                        'dest_address': str(original_dest),
                        'next_hop': str(netaddr.IPNetwork(possible_ip[1]).ip),
                        'state': 'merged'
                    }
                ]},
                data_dir=os.path.abspath('../ansible/')
            )
            if self.check_fix():
                logger.info("Loop fixed")
                return True
        logger.info(f"Possible IP pair not found with {last_node_from_dest} - {last_node_in_loop}")
        return False

    def fix_loop(self) -> bool:
        """
        Fix the loop in the network. This works after the loop type is determined.
        :return: True if the loop was fixed, False otherwise
        """
        logger.debug("Init fixing loop")
        state = self.detect_loop_in_route()
        if state['source']['loop']:
            logger.debug("Loop from source to destination detected")
            last_node_from_dest = self.traverse_route(
                self.graph_from_source.reverse(copy=True), 'PC-D', 'PC-S')
            logger.debug(f"Last node from destination: {last_node_from_dest}")
            for last_node_in_loop in reversed(state['source']['members']):
                if self.check_and_fix_loop(last_node_in_loop, last_node_from_dest, self.destination.network):
                    return True
            logger.warning("No possible fix found!")
        if state['destination']['loop']:
            logger.debug("Loop from destination to source detected")
            last_node_from_source = self.traverse_route(
                self.graph_from_destination.reverse(copy=True), 'PC-S', 'PC-D')
            logger.debug(f"Last node from source: {last_node_from_source}")
            for last_node_in_loop in reversed(state['destination']['members']):
                if self.check_and_fix_loop(last_node_in_loop, last_node_from_source, self.source.network):
                    return True
            logger.warning("No possible fix found!")
        return False

    def __str__(self) -> str:
        ret_string = ""
        for host in self.hosts:
            ret_string += str(host) + "\n"
        return ret_string

    def __repr__(self) -> str:
        return f"NetworkAnalyzer({str(self.hosts)})"
