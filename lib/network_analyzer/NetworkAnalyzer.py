import logging
import networkx as nx
import matplotlib.pyplot as plt

from network_analyzer.Host import Host
from network_analyzer.exception.exception import NodeNotFoundException
from utils.ip import compare_cidr_and_ip_address

logger = logging.getLogger(__name__)

class NetworkAnalyzer:
    hosts = []
    graph = nx.DiGraph()
    
    def __init__(self, facts):
        # Create a new host for every fact element
        # Add the hosts to the hosts directive
        for hostname, host_facts in facts.items():
            logger.debug(f"Adding host {hostname}")
            self.hosts.append(Host(host_facts))
        logger.debug("Hosts loaded")
        self.init_graph()
        
    def init_graph(self):
        # Create an initial graph of the network
        # Go through the network hosts
        edges = []
        for host in self.hosts:
            # Get all routes of a host
            for table in host.routes:
                # Filter VRF routes. In our environment, VRF routes only represent management network access
                # which we would like to filter from our real network.
                if 'vrf' not in table:
                    for route in table['address_families']:
                        edges.append(self.create_graph_edge(host, route['routes'][0]['next_hops'][0]['forward_router_address']))
        self.graph.add_edges_from(edges)
        logger.debug("Network initialization complete")
    
    def create_graph_edge(self, host, source_ip):
        # Create a graph edge with source ip (IP address of current host)
        # and finding the opposite side of the link in one of the available hosts.
        try:
            dest_host = self.find_host_with_ip_address(source_ip)
        except NodeNotFoundException as e:
            logger.warning(e)
        else:
            return (host.hostname, dest_host.hostname)
    
    def detect_loop(self):
        # Check if the current graph contains a loop.
        for loop in nx.simple_cycles(self.graph):
            current_loop = loop.copy()
        
        
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

    def plot_graph(self):
        # Plot the graph to a file
        # Used for debugging and creating visualizations for thesis.
        planar = nx.planar_layout(self.graph)
        nx.draw_networkx_nodes(self.graph, planar, node_color='tab:blue', edgecolors="black", node_size=800, alpha=1)
        nx.draw_networkx_edges(self.graph, planar, edgelist=self.graph.edges(), arrowsize=30, width=2, edge_color="black")
        nx.draw_networkx_labels(self.graph, planar, font_color="whitesmoke")
        # Show the graph
        plt.savefig('plot.png')
        logger.info("Plot saved to file!")
        
    def __str__(self):
        ret_string = ""
        for host in self.hosts:
            ret_string += str(host) + "\n"
        return ret_string
