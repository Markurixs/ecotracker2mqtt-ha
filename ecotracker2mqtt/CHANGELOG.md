# Changelog

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
