# Protocolo JSON unificado

```json
{
  "proto": "dijkstra|flooding|lsr|dvr",
  "type":  "message|echo|info|hello",
  "from":  "N1",
  "to":    "N10",
  "ttl":   5,
  "headers": [{"k":"v"}],
  "payload": {}
}
```

- `message`: datos de usuario (`payload.text` opcional)
- `hello`/`echo`: medición de latencia y descubrimiento de vecinos
- `info`: intercambio de vectores (DVR) o LSPs (LSR)
