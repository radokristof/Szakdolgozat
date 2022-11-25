from typing import Union

import netaddr  # type: ignore


def compare_cidr_and_ip_address(cidr_ip: str, ip_address: str) -> bool:
    """
    Compare CIDR IP Address (192.168.30.1/30) with pure IP address (192.168.30.1)
    :param cidr_ip: The CIDR IP Address in string format
    :param ip_address: The IP address in string format
    :return: True if the IP addresses match, False if they are not the same.
    """
    return netaddr.IPNetwork(cidr_ip).ip == netaddr.IPAddress(ip_address)


def check_network_contains_ip(ip_address: Union[str, netaddr.IPAddress], network: Union[str, netaddr.IPNetwork]) \
        -> bool:
    """
    Check if the provided ip_address is in the provided network
    :param ip_address: The IP address to check
    :param network: The network where the IP address should be in
    :return: True if the IP address belongs to the network, False if it does not
    """
    return netaddr.IPAddress(ip_address) in netaddr.IPNetwork(network)


def check_network_contains_network(contained_network: Union[str, netaddr.IPNetwork],
                                   containing_network: Union[str, netaddr.IPNetwork]) -> bool:
    """
    Check if the contained_network is in the containing network (Eg.: 192.168.1.0/24 is in 192.168.1.0/22)
    Filter default routes
    :param contained_network: The network which should be contained
    :param containing_network: The network which should contain the contained_network
    :return: True if the containing_network contains the contained_network, False if it does not
    """
    if netaddr.IPNetwork(containing_network) == netaddr.IPNetwork('0.0.0.0/0'):
        return False
    return netaddr.IPNetwork(contained_network) in netaddr.IPNetwork(containing_network)


def check_network_is_in_supernet(contained_network: Union[str, netaddr.IPNetwork],
                                 containing_network: Union[str, netaddr.IPNetwork]) -> bool:
    """
    Check if the provided network is in a private supernet (Eg.: 10.0.1.0/24 is in 10.0.0.0/16)
    Also check if the current network is private or not. If it is private, only check private supernets.
    Otherwise, check all
    :param contained_network: The network which should be contained in the supernet
    :param containing_network: The supernet which should contain the contained_network
    :return: True if the containing_network contains the contained_network, False if it does not
    """
    net = netaddr.IPNetwork(contained_network)
    private = net.is_private()
    supernets = net.supernet()
    network_to_check = netaddr.IPNetwork(containing_network)
    for network in supernets:
        # Only check if the provided network is private and the checked network is also private
        # If the provided network is not private, always check
        if (private and network.is_private()) or not private:
            if network_to_check == network:
                return True
    return False
