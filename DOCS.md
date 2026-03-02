# EcoTracker MQTT Bridge

Liest die Daten des everHome EcoTracker per lokaler HTTP API aus und
publiziert sie sekündlich per MQTT.

## MQTT Auto-Discovery

Wenn der **Mosquitto Add-on** in Home Assistant installiert ist, werden
die MQTT-Zugangsdaten automatisch erkannt. Das Feld `mqtt_host` kann
dann leer bleiben.

Für einen externen MQTT-Broker `mqtt_host`, `mqtt_port`, `mqtt_user`
und `mqtt_password` manuell setzen.

## MQTT Topics

| Topic                          | Inhalt                        |
| ------------------------------ | ----------------------------- |
| `ecotracker/json`              | Kompletter JSON-String        |
| `ecotracker/power`             | Aktuelle Leistung (W)         |
| `ecotracker/powerAvg`          | Durchschnittsleistung (W)     |
| `ecotracker/powerPhase1`       | Phase 1 (W)                   |
| `ecotracker/powerPhase2`       | Phase 2 (W)                   |
| `ecotracker/powerPhase3`       | Phase 3 (W)                   |
| `ecotracker/energyCounterIn`   | Zählerstand Bezug (kWh)       |
| `ecotracker/energyCounterOut`  | Zählerstand Einspeisung (kWh) |
| `ecotracker/agePower`          | Alter des Messwerts (ms)      |
| `ecotracker/status`            | `online` / `offline`          |

Der Topic-Prefix (`ecotracker`) ist in den Optionen konfigurierbar.

## Konfiguration

| Option              | Standard                              | Beschreibung                          |
| ------------------- | ------------------------------------- | ------------------------------------- |
| `ecotracker_url`    | `http://192.168.44.233/v1/json`       | URL der EcoTracker API                |
| `poll_interval`     | `1`                                   | Abfrageintervall in Sekunden          |
| `mqtt_host`         | *(leer = Auto-Discovery)*             | MQTT Broker Hostname/IP               |
| `mqtt_port`         | `1883`                                | MQTT Broker Port                      |
| `mqtt_user`         | *(leer)*                              | MQTT Benutzername                     |
| `mqtt_password`     | *(leer)*                              | MQTT Passwort                         |
| `mqtt_topic_prefix` | `ecotracker`                          | Prefix für alle MQTT Topics           |
| `mqtt_qos`          | `0`                                   | MQTT Quality of Service (0, 1, 2)     |
| `mqtt_retain`       | `true`                                | MQTT Retain Flag                      |
| `log_level`         | `info`                                | Log-Level (debug, info, warning, error) |
