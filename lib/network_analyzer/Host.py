import logging

logger = logging.getLogger(__name__)

class Host:
    hostname = 'R0'
    interfaces = None
    routes = None
    
    # Extract useful info from the received facts dict.
    def __init__(self, facts):
        self.hostname = facts['ansible_net_hostname']
        self.interfaces = facts['ansible_network_resources']['l3_interfaces']
        self.routes = facts['ansible_network_resources']['static_routes']
        logger.debug("Host {} loaded".format(str(self.hostname)))
        
    def __str__(self):
        return "[{}] - Interfaces: {}\nRoutes: {}".format(self.hostname, str(self.interfaces), str(self.routes))
