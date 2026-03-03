# Changelog

## 1.4.4

- Fix: Flask bindet nur noch auf `127.0.0.1` — Port nicht mehr extern erreichbar

## 1.4.3

- Fix: Werkzeug Request-Logging unterdrückt — keine "GET /api/logs" Zeilen mehr im Live-Log

## 1.4.2

- Fix: Ingress-Port von 8099 auf 8098 geändert — Konflikt mit Hoymiles Add-on bei `host_network: true`

## 1.4.1

- HTML Log-Viewer direkt in Python eingebettet — kein separates `www/` Verzeichnis mehr
- `www/` Ordner und `index.html` entfernt
- `pathlib` / `send_from_directory` Abhängigkeiten entfernt

## 1.4.0

- Live-Log in der HA Seitenleiste via Ingress
- Zeigt die letzten 500 Log-Zeilen in Echtzeit (1s Refresh)
- Farbiges Log-Level Highlighting (ERROR rot, WARNING orange, DEBUG grau)
- Auto-Scroll mit manueller Scroll-Pause

## 1.3.0

- HA MQTT Discovery: Sensoren erscheinen automatisch in Home Assistant
- Device "EcoTracker" (everHome) mit allen Sensoren gruppiert
- Korrekte device_class/state_class für Energy Dashboard Kompatibilität
- `agePower` als diagnostischer Sensor

## 1.2.1

- Fix: Subnet-Erkennung nutzt jetzt `ip addr` statt `socket.getaddrinfo` — erkennt das tatsächliche Subnetz korrekt (auch /21, /22 etc.)
- Kein Fallback auf hardcoded Subnetze mehr

## 1.2.0

- EcoTracker Auto-Discovery: scannt das lokale Netzwerk automatisch wenn `ecotracker_host` leer ist
- Erkennt den EcoTracker anhand der `/v1/json` API-Antwort (`power` + `energyCounterIn`)
- Paralleler Subnet-Scan (50 Threads, ~5 Sekunden für ein /24 Netz)
- `ecotracker_host` ist jetzt optional — leer lassen für Auto-Discovery

## 1.1.1

- Fix: `SUPERVISOR_TOKEN` war nicht verfügbar wegen s6-overlay — `run.sh` mit `with-contenv` eingeführt

## 1.1.0

- MQTT Broker-Erkennung gefixt: Fallback auf Supervisor-IP (172.30.32.2) bei host_network
- Docker-Hostname `core-mosquitto` wird automatisch auf `127.0.0.1` gemappt
- `services: mqtt:want` in config.yaml hinzugefügt
- Logging bei MQTT-Erkennung auf WARNING/INFO hochgestuft
- Konfiguration vereinfacht: nur noch IP/Hostname statt voller URL
- Repo-Struktur korrigiert (Add-on in Subdirectory)
- CHANGELOG.md in Add-on-Verzeichnis verschoben (HA-kompatibel)
- Install-Button für Home Assistant in README

## 1.0.1

- Erster Fix MQTT Auto-Detect
## 1.0.0

- Initiales Release
- Pollt EcoTracker HTTP API sekündlich
- Publiziert alle Messwerte als einzelne MQTT Topics + JSON
- Automatische Erkennung des Mosquitto Broker Add-ons
- Last-Will Testament (`ecotracker/status`)
- Multi-Arch Support (amd64, aarch64, armhf, armv7, i386)
- Konfigurierbar über die Home Assistant Add-on UI
