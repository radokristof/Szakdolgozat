import netaddr

def compare_cidr_and_ip_address(cidr_ip, ip_address):
    # Compare CIDR IP Address (192.168.30.1/30) with pure IP address (192.168.30.1)
    # Returns true if the IP addresses match, False if they are not the same.
    return netaddr.IPNetwork(cidr_ip).ip == netaddr.IPAddress(ip_address)
