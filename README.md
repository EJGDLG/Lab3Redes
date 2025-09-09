# Routing Lab UVG 2025 — Redis/XMPP-Compatible Prototype


## Cómo correr
1) Crear venv (opcional) e instalar dependencias
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Levantar un nodo (ejemplo N1 en modo LSR)
```bash
# Ventana N3 (ya tienes N3 corriendo ahí)
python -m src.run_node --id N3  --proto lsr --topo config/topology_11_nodes.json --names config/names_example.json
# Ventana N1
python -m src.run_node --id N1  --proto lsr --topo config/topology_11_nodes.json --names config/names_example.json
# Ventana N10
python -m src.run_node --id N10 --proto lsr --topo config/topology_11_nodes.json --names config/names_example.json
# Ventana N5
python -m src.run_node --id N5 --proto lsr --topo config/topology_11_nodes.json --names config/names_example.json

# Ventana N6
python -m src.run_node --id N6 --proto lsr --topo config/topology_11_nodes.json --names config/names_example.json

```
3) Enviar un mensaje de **usuario** de N1 a N10
```bash
python -m src.tools.send_message --from N1 --to N5 --text "Hola desde N1 ??" --proto lsr --names config/names_example.json
#mensaje 2
python -m src.tools.send_message --from N1 --to N3 --text "Hola desde N1 ??" --proto lsr --names config/names_example.json
```

4) Cambiar de algoritmo:
- Flooding: `--proto flooding`
- Distance Vector: `--proto dvr`
- Link-State: `--proto lsr` (usa Dijkstra internamente)

## Variables de entorno (opcionales)
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
- `HELLO_INTERVAL` (segundos, default 5)
- `INFO_INTERVAL` (segundos, default 8)
- `TTL_DEFAULT` (default 8)

## Notas
- El archivo de **topología** se usa sólo para que **cada nodo** conozca a sus vecinos directos.
- `names_example.json` mapea IDs a canales/usuarios (en Redis usamos un canal por nodo).
- Todo el *I/O* de red es no bloqueante con `asyncio`.
- La tabla de ruteo se imprime al estabilizar o al recibir nueva info.
