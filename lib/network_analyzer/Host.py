import logging
import netaddr  # type: ignore

logger = logging.getLogger(__name__)


class Host:
    hostname = 'R0'
    interfaces = None
    routes = None
    
    # Extract useful info from the received facts' dict.
    def __init__(self, facts: dict):
        self.hostname = facts['ansible_net_hostname']
        self.interfaces = facts['ansible_network_resources']['l3_interfaces']
        # Merging different interface variables (interface, l2_interface, l3_interface).
        # All of them should have distinct objects. Only name is the same.
        for index, interface in enumerate(self.interfaces):
            raw_interface = list(filter(lambda intf, curr_interface=interface: intf['name'] == curr_interface['name'],
                                        facts['ansible_network_resources']['interfaces']))[0]
            l2_interface = list(filter(lambda intf, curr_interface=interface: intf['name'] == curr_interface['name'],
                                       facts['ansible_network_resources']['l2_interfaces']))[0]
            merge = {**interface, **raw_interface, **l2_interface}
            self.interfaces[index] = merge
            logger.debug(f"Current element: {self.interfaces[index]}")
        self.routes = facts['ansible_network_resources']['static_routes']
        self.facts = facts
        logger.debug("Host {} loaded".format(str(self.hostname)))
        
    def __str__(self):
        return "[{}] - Interfaces: {}\nRoutes: {}".format(self.hostname, str(self.interfaces), str(self.routes))


class SourceHost(Host):
    # SourceHost contains the source network.
    def __init__(self, source: netaddr.IPNetwork, facts: dict):
        self.network = source
        logger.debug("Init SourceHost")
        super().__init__(facts)


class DestinationHost(Host):
    # DestinationHost contains the destination network.
    def __init__(self, destination: netaddr.IPNetwork, facts: dict):
        self.network = destination
        logger.debug("Init DestinationHost")
        super().__init__(facts)
