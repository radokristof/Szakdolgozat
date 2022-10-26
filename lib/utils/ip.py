import netaddr

def compare_cidr_and_ip_address(cidr_ip, ip_address):
    # Compare CIDR IP Address (192.168.30.1/30) with pure IP address (192.168.30.1)
    # Returns true if the IP addresses match, False if they are not the same.
    return netaddr.IPNetwork(cidr_ip).ip == netaddr.IPAddress(ip_address)

def check_network_contains_ip(ip_address, network):
    # Check if the provided ip_address is in the provided network
    return netaddr.IPAddress(ip_address) in netaddr.IPNetwork(network)

def check_network_contains_network(contained_network, containing_network):
    # Check if the contained_network is in the containing network (Eg.: 192.168.1.0/24 is in 192.168.1.0/22)
    return netaddr.IPNetwork(contained_network) in netaddr.IPNetwork(containing_network)
