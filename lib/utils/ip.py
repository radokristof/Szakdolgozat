import netaddr  # type: ignore


def compare_cidr_and_ip_address(cidr_ip: str, ip_address: str) -> bool:
    """
    Compare CIDR IP Address (192.168.30.1/30) with pure IP address (192.168.30.1)
    :param cidr_ip: The CIDR IP Address in string format
    :param ip_address: The IP address in string format
    :return: True if the IP addresses match, False if they are not the same.
    """
    return netaddr.IPNetwork(cidr_ip).ip == netaddr.IPAddress(ip_address)


def check_network_contains_ip(ip_address: str, network: str) -> bool:
    """
    Check if the provided ip_address is in the provided network
    :param ip_address: The IP address to check
    :param network: The network where the IP address should be in
    :return: True if the IP address belongs to the network, False if it does not
    """
    return netaddr.IPAddress(ip_address) in netaddr.IPNetwork(network)


def check_network_contains_network(contained_network: str, containing_network: str) -> bool:
    """
    Check if the contained_network is in the containing network (Eg.: 192.168.1.0/24 is in 192.168.1.0/22)
    :param contained_network: The network which should be contained
    :param containing_network: The network which should contain the contained_network
    :return: True if the containing_network contains the contained_network, False if it does not
    """
    return netaddr.IPNetwork(contained_network) in netaddr.IPNetwork(containing_network)
