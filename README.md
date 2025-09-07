# README reconstruido con soporte XMPP parametrizable\n
# Ventana 2
python run_node.py --id B --algo dvr --config-dir config --transport socket --log INFO
# Ventana 3
python run_node.py --id C --algo flooding --config-dir config --transport socket --log INFO
# prueba un envío de A para los demas:
python run_node.py --id A --algo lsr --config-dir config --transport socket --send C "Hola C por sockets"

