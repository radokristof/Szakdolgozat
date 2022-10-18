from ansible_api.playbook import run_playbook

run_playbook(inventory_file='../ansible/hosts.yml', playbook_file='../ansible/playbooks/initial-network.yml')
