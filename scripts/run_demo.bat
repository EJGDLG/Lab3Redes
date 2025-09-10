@echo off
start cmd /k python -u src\run_node.py --id N1 --proto lsr --topo config\topology_11_nodes.json --names config\names_example.json
start cmd /k python -u src\run_node.py --id N3 --proto lsr --topo config\topology_11_nodes.json --names config\names_example.json
start cmd /k python -u src\run_node.py --id N10 --proto lsr --topo config\topology_11_nodes.json --names config\names_example.json
timeout /t 10
python -u src\tools\send_message.py --from N1 --to N10 --text "Hola N10!" --proto lsr --names config\names_example.json
