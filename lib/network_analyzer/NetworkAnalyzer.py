import logging
import networkx as nx
import netaddr
import matplotlib.pyplot as plt

from network_analyzer.Host import Host, SourceHost, DestinationHost
from network_analyzer.exception.exception import NodeNotFoundException, NetworkSourceDestinationException, NetworkMultipleDefinitionException
from utils.ip import compare_cidr_and_ip_address

logger = logging.getLogger(__name__)

class NetworkAnalyzer:
    hosts = []
    graph = nx.DiGraph()
    source = None
    destination = None
    
    errors = []
    
    def __init__(self, facts, source, destination):
        # Create a new host for every fact element
        # Add the hosts to the hosts directive
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
        
    def init_graph(self):
        # Create an initial graph of the network
        # Go through the network hosts
        edges = []
        for host in self.hosts:
            # Get all routes of a host
            for table in host.routes:
                edge = self.create_route_edge(host, table)
                if edge:
                    edges.append(edge)
            for interface in host.interfaces:
                edge = self.create_pc_edge(host, interface)
                if edge:
                    edges.append(edge)
        self.graph.add_edges_from(edges)
        logger.debug("Network initialization complete")
    
    def init_network(self, source, destination):
        # Initialize network, find source and destination networok provided by the user.
        # If these networks cannot be found in the current hosts, the program will exit.
        source_found = False
        destination_found  = False
        for host in self.hosts:
            for interface in host.interfaces:
                net = self.check_source_destination(interface, source, destination)
                if net == "source" and source_found:
                    raise NetworkMultipleDefinitionException(f"The network {str(destination)} is defined multiple times in the network")
                elif net == "source":
                    self.source = SourceHost(source, host.facts)
                    source_found = True
                elif net == "destination" and destination_found:
                    raise NetworkMultipleDefinitionException(f"The network {str(destination)} is defined multiple times in the network")
                elif net == "destination":
                    self.destination = DestinationHost(destination, host.facts)
                    destination_found = True
        if source_found and destination_found:
            logger.info("Source and destination network found!")
        else:
            raise NetworkSourceDestinationException("Network source or destination not found in the network!")
    
    def check_source_destination(self, interface, source, destination):
        # Check for source and destination network/IP address.
        # This route will be checked against loops and other factors which might influence the routing capabilities.
        if 'ipv4' in interface:
            ip_addr = netaddr.IPNetwork(interface['ipv4'][0]['address'])
            # Comparing received address (eg: 192.168.1.1/24) with network address from config: 192.168.1.0/24
            if ip_addr == source:
                return "source"
            # Comparing received address (eg: 192.168.1.1/24) with network address from config: 192.168.1.0/24
            elif ip_addr == destination:
                return "destination"
        return None
    
    def create_graph_edge(self, host, source_ip):
        # Create a graph edge with source ip (IP address of current host)
        # and finding the opposite side of the link in one of the available hosts.
        try:
            dest_host = self.find_host_with_ip_address(source_ip)
        except NodeNotFoundException as e:
            logger.warning(e)
        else:
            return (host.hostname, dest_host.hostname)
    
    def create_route_edge(self, host, table):
        # Filter VRF routes. In our environment, VRF routes only represent management network access
        # which we would like to filter from our real network.
        if 'vrf' not in table:
            for route in table['address_families']:
                # Filter routes based on destination. If the current route is not destinated towards our destination network, ignore it.
                if netaddr.IPNetwork(route['routes'][0]['dest']) == self.destination.network:
                    return self.create_graph_edge(host, route['routes'][0]['next_hops'][0]['forward_router_address'])
        return None
    
    def create_pc_edge(self, host, interface):
        # Create static PC nodes in the graph. These represent the computers used in network troubleshooting.
        # PC-S will be the Source PC (this will be placed at the source network)
        # PC-D will be the Destination PC (this will be placed at the destination network)
        if 'ipv4' in interface:
            if netaddr.IPNetwork(interface['ipv4'][0]['address']) == self.source.network:
                return ('PC-S', host.hostname)
            elif netaddr.IPNetwork(interface['ipv4'][0]['address']) == self.destination.network:
                return (host.hostname, 'PC-D')
        return None
    
    def detect_loop_in_route(self):
        # Check if the current graph contains a loop.
        current_loop = None
        for loop in nx.simple_cycles(self.graph):
            current_loop = loop.copy()
        # The current_loop var is empty if there are no loops in the network
        if current_loop:
            if nx.hash_path(self.graph, self.source.hostname, self.destination.hostname):
                # It has a loop, but the path is clear towards the destination, so the current route is unaffected.
                return {"loop": True, "affected": False, "members": current_loop}
            # It has a loop and the path is not clear towards the destination.
            return {"loop": True, "affected": True, "members": current_loop}
        # Check if there is no loop, the route is still functional
        else:
            # If it has path and there is no loop, the network seems healthy.
            if nx.has_path(self.graph, self.source.hostname, self.destination.hostname):
                return {"loop": False, "affected": False}
            # No loop, but there is no route to the destination - maybe a rupture in the route.
            else:
                return {"loop": False, "affected": True}
        
    def find_host_with_ip_address(self, ip_address):
        # Check if a host has an IP Address
        # Parameter ip_address is a normal ip address with dot notation. Like: 192.168.10.1
        # Interface IP address is in CIDR notation. Like: 192.168.10.1/30
        for host in self.hosts:
            for interface in host.interfaces:
                # If an interface does not have an IP address, it will not have an 'ipv4' key
                if 'ipv4' in interface:
                    # Check if the current IP address (network) is the same as the received ip_address.
                    if compare_cidr_and_ip_address(interface['ipv4'][0]['address'], ip_address):
                        return host
        # Raise error if the current IP address cannot be found in the network.
        raise NodeNotFoundException(f"Not found {ip_address}")

    def plot_graph(self, filename):
        # Plot the graph to a file
        # Used for debugging and creating visualizations for thesis.
        planar = nx.planar_layout(self.graph)
        nx.draw_networkx_nodes(self.graph, planar, node_color='tab:blue', edgecolors="black", node_size=800, alpha=1)
        nx.draw_networkx_edges(self.graph, planar, edgelist=self.graph.edges(), arrowsize=30, width=2, edge_color="black")
        nx.draw_networkx_labels(self.graph, planar, font_color="whitesmoke")
        # Show the graph
        plt.savefig(filename)
        logger.info("Plot saved to file!")
        
    def __str__(self):
        ret_string = ""
        for host in self.hosts:
            ret_string += str(host) + "\n"
        return ret_string
    
    def __repr__(self):
        return f"NetworkAnalyzer({str(self.hosts)})"
