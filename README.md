# HealthMonitor

Motore Python per il progetto **Monitor Salute** (Jira `MS-2`). Espone una Web API
che la dashboard può interrogare; il primo dispositivo supportato è lo
**Huawei Watch GT 3 Pro**.

## Percorso dati GT3 Pro

Il GT3 Pro **non** si collega in BLE aperto da questo PC in modo ufficiale.
Il flusso supportato:

```
GT3 Pro  →  app Huawei Health (telefono)  →  Health Kit cloud  →  HealthMonitor  →  Dashboard
```

Serve un’app Huawei Developer con Health Kit abilitato, OAuth Huawei ID e scope
lettura (es. heart rate, SpO₂, sleep, steps, stress).

## Avvio rapido

```bash
cd C:\FUDE\servizi\HealthMonitor
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.ini config.ini
# compila client_id / client_secret / refresh_token
python -m healthmonitor
```

API di default: `http://127.0.0.1:8090`

| Metodo | Path | Uso |
|--------|------|-----|
| GET | `/api/health` | liveness |
| GET | `/api/status` | stato motore + ultimo device |
| GET | `/api/devices/huawei-gt3-pro` | snapshot GT3 Pro |
| POST | `/api/devices/huawei-gt3-pro/sync` | sync on-demand |
| GET | `/api/metrics/latest` | metriche per dashboard |

Senza credenziali Huawei il motore resta in **modalità demo** (snapshot vuoto + note).

## Versione

Vedi `healthmonitor/version.py` (`ENGINE_VERSION`).
