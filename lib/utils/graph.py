import logging
from typing import Union, List, Tuple

import netaddr
import networkx as nx
from networkx.classes.reportviews import OutEdgeView

from network_analyzer.Host import Host
from network_analyzer.exception.exception import InterfaceNotFound
from utils.ip import check_network_contains_ip, check_network_contains_network

logger = logging.getLogger(__name__)


def get_interface_status_from_route(host: Host, ip_address: str) -> bool:
    """
    Check an interface enabled status based on host IP addresses.
    Returns the interface status in a host based on the IP address of the next-hop interface.
    The IP address will be checked if the current interface network contains that IP address.
    If the IP address does not match any interface on the current host, InterfaceNotFound error will be raised
    :param host: The host object with interfaces
    :param ip_address: The IP address to check
    :return: True if the interface of that IP address is enabled, False if it is disabled
    :raises: InterfaceNotFound if the IP address does not match any interface on the host
    """
    logger.debug(f"Searching interface for IP address {ip_address}")
    for interface in host.interfaces:
        if 'ipv4' in interface:
            if check_network_contains_ip(ip_address, interface['ipv4'][0]['address']):
                return interface['enabled']
    raise InterfaceNotFound(f"Can't find interface for IP address {ip_address}")


def get_route_from_interface(host: Host, interface: dict, source: netaddr.IPNetwork, destination: netaddr.IPNetwork) \
        -> bool:
    """
    Get the route from a host based on the interface
    :param destination: The destination network/IP address
    :param source: The source network/IP address
    :param host: The host object
    :param interface: The interface object
    :return: The route object if found, None if not found
    """
    for table in host.routes:
        if 'vrf' not in table:
            for route in table['address_families']:
                if check_network_contains_ip(route['routes'][0]['next_hops'][0]['forward_router_address'],
                                             interface['ipv4'][0]['address']):
                    if check_network_contains_network(str(source), route['routes'][0]['dest']) or \
                            check_network_contains_network(str(destination), route['routes'][0]['dest']):
                        return True
    return False


def check_interface_status(host: Host, source: netaddr.IPNetwork, destination: netaddr.IPNetwork) -> list:
    """
    Get all interface statutes from a host
    :param destination: The source network which needs to be enabled
    :param source: The destination network which needs to be enabled
    :param host: The host object
    :return: list of interface statuses
    """
    down_interfaces = []
    for interface in host.interfaces:
        if 'ipv4' in interface and not interface['enabled']:
            if get_route_from_interface(host, interface, source, destination):
                down_interfaces.append({'name': interface['name'], 'description': interface['description']})
    return down_interfaces


def get_graph_difference(new_graph: nx.DiGraph, old_graph: nx.DiGraph) -> nx.DiGraph:
    """
    Get difference between two graphs.
    This will show which edges exist in the new graph, which is not in the old graph
    :param new_graph: The newer graph where new edges/nodes might be added
    :param old_graph: The older/initial graph which will be compared to the newer one.
    :return:
    """
    return nx.difference(new_graph, old_graph)


def check_source_destination(interface: dict, source: netaddr.IPNetwork, destination: netaddr.IPNetwork) \
        -> Union[str, None]:
    """
    Check for source and destination network/IP address.
    This route will be checked against loops and other factors which might influence the routing capabilities.
    :param interface: The interface containing the IP address(es)
    :param source: The source network/IP address
    :param destination: The destination network/IP address
    :return: str based on the result. Will return 'source' if this is a source route, 'destination' if this is a
    destination route, None if this is not a source or destination route.
    """
    if 'ipv4' in interface:
        ip_addr = netaddr.IPNetwork(interface['ipv4'][0]['address'])
        # Comparing received address (eg: 192.168.1.1/24) with network address from config: 192.168.1.0/24
        if ip_addr == source:
            return "source"
        # Comparing received address (eg: 192.168.1.1/24) with network address from config: 192.168.1.0/24
        elif ip_addr == destination:
            return "destination"
    return None


def get_new_edges(initial_graph, current_graph) -> OutEdgeView:
    """
    Get which edges were added to the current graph, compared to the initial state
    :param initial_graph:
    :param current_graph:
    :return:
    """
    return get_graph_difference(current_graph, initial_graph).edges


def get_removed_edges(initial_graph: nx.DiGraph, current_graph: nx.DiGraph) -> OutEdgeView:
    """
    Get which edges were removed from the current graph, compared to the initial state
    :param initial_graph:
    :param current_graph:
    :return:
    """
    return get_graph_difference(initial_graph, current_graph).edges


def check_loop_type(graph: nx.DiGraph, loop: List[str], source: str, destination: str) -> dict:
    """

    :param graph:
    :param loop:
    :param source:
    :param destination:
    :return:
    """
    if loop:
        if nx.has_path(graph, source, destination):
            # It has a loop, but the path is clear towards the destination, so the current route is unaffected.
            return {"loop": True, "affected": False, "members": loop}
        # It has a loop and the path is not clear towards the destination.
        return {"loop": True, "affected": True, "members": loop}
    # Check if there is no loop, the route is still functional
    else:
        # If it has path and there is no loop, the network seems healthy.
        if nx.has_path(graph, source, destination):
            return {"loop": False, "affected": False}
        # No loop, but there is no route to the destination - maybe a rupture in the route.
        else:
            return {"loop": False, "affected": True}


def generate_tmp_graph(name: str, graph: nx.DiGraph, initial_graph: nx.DiGraph) -> nx.DiGraph:
    """

    :param name:
    :param graph:
    :param initial_graph:
    :return:
    """
    tmp_graph = graph
    new_edges = get_new_edges(initial_graph, graph)
    removed_edges = get_removed_edges(initial_graph, graph)
    tmp_graph.add_edges_from(new_edges, color='green', weight=2, style='--', label='Added edge')
    for source, destination in removed_edges:
        nx.set_edge_attributes(tmp_graph, {(source, destination): {"color": 'red',
                                                                   "label": 'Removed edge',
                                                                   "style": '--'
                                                                   }})
    logger.debug(f"{name} new edges: {new_edges}")
    logger.debug(f"{name} removed edges: {removed_edges}")
    logger.debug(f"{name} graph edges: {tmp_graph.edges(data=True)}")
    return tmp_graph


def check_missing_interface_route(host: Host) -> list:
    missing_routes = []
    for interface in host.interfaces:
        if 'ipv4' in interface:
            addr = interface['ipv4'][0]['address']
            found = False
            for table in host.routes:
                for route in table['address_families']:
                    if check_network_contains_ip(route['routes'][0]['next_hops'][0]['forward_router_address'],
                                                 addr):
                        logger.debug(f"Found route for {addr} in {host.hostname}")
                        found = True
            if not found:
                logger.debug(f"Missing route for {addr} in {host.hostname}")
                missing_routes.append(addr)
    return missing_routes


def get_interface_ip_within_ip_network(host: Host, ip_addresses: List[str]) -> Union[str, None]:
    for interface in host.interfaces:
        if 'ipv4' in interface:
            addr = interface['ipv4'][0]['address']
            for ip_address in ip_addresses:
                if check_network_contains_network(addr, ip_address):
                    return addr
    return None
