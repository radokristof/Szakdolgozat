import logging
from typing import Union
import networkx as nx
import netaddr

from network_analyzer.Host import Host
from network_analyzer.exception.exception import InterfaceNotFound
from utils.ip import check_network_contains_ip

logger = logging.getLogger(__name__)


def get_interface_status_from_route(host: Host, ip_address: str) -> bool:
    """
    Check an interface enabled status based on host IP addresses.
    Returns the interface status in a host based on the IP address of the next-hop interface.
    The IP address will be checked if the current interface network contains that IP address.
    If the IP address does not match any interface on the current host, InterfaceNotFound error will be raised.
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


def check_interface_status(host: Host) -> list:
    """
    Get all interface statutes from a host
    :param host: The host object
    :return: list of interface statuses
    """
    down_interfaces = []
    for interface in host.interfaces:
        if 'ipv4' in interface and not interface['enabled']:
            down_interfaces.append({'name': interface['name'], 'description': interface['description']})
    return down_interfaces


def get_graph_difference(new_graph, old_graph):
    """
    Get difference between two graphs.
    This will show which edges exist in the new graph, which is not in the old graph.
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
