# eco2mqtt

Home Assistant Add-on: Liest den [everHome EcoTracker](https://everhome.cloud) per lokaler HTTP API aus und publiziert alle Werte sekündlich per MQTT.

## Installation

1. In Home Assistant: **Einstellungen → Add-ons → Add-on Store → ⋮ → Repositories**
2. Repository-URL eintragen:
   ```
   https://github.com/Markurixs/eco2mqtt
   ```
3. **EcoTracker MQTT Bridge** installieren
4. Unter **Konfiguration** die IP des EcoTrackers prüfen und ggf. anpassen
5. Add-on starten

> Wenn der **Mosquitto Broker** Add-on installiert ist, wird MQTT automatisch erkannt — `mqtt_host` kann leer bleiben.

## MQTT Topics

Alle Werte werden einzeln und als JSON publiziert (retained, QoS konfigurierbar).

| Topic                          | Inhalt                        | Beispiel     |
| ------------------------------ | ----------------------------- | ------------ |
| `ecotracker/json`              | Kompletter JSON-String        | `{"power":-282, …}` |
| `ecotracker/power`             | Aktuelle Leistung (W)         | `-282`       |
| `ecotracker/powerAvg`          | Durchschnittsleistung (W)     | `-50`        |
| `ecotracker/powerPhase1`       | Phase 1 (W)                   | `-904`       |
| `ecotracker/powerPhase2`       | Phase 2 (W)                   | `370`        |
| `ecotracker/powerPhase3`       | Phase 3 (W)                   | `251`        |
| `ecotracker/energyCounterIn`   | Zählerstand Bezug (kWh)       | `3417631.8`  |
| `ecotracker/energyCounterOut`  | Zählerstand Einspeisung (kWh) | `215770.5`   |
| `ecotracker/agePower`          | Alter des Messwerts (ms)      | `500`        |
| `ecotracker/status`            | Online-Status                 | `online` / `offline` |

Der Topic-Prefix (`ecotracker`) ist konfigurierbar.

## Konfiguration

| Option              | Standard                              | Beschreibung                            |
| ------------------- | ------------------------------------- | --------------------------------------- |
| `ecotracker_url`    | `http://192.168.44.233/v1/json`       | URL der EcoTracker API                  |
| `poll_interval`     | `1`                                   | Abfrageintervall in Sekunden            |
| `mqtt_host`         | *(leer = Auto-Discovery)*             | MQTT Broker Hostname/IP                 |
| `mqtt_port`         | `1883`                                | MQTT Broker Port                        |
| `mqtt_user`         | *(leer)*                              | MQTT Benutzername                       |
| `mqtt_password`     | *(leer)*                              | MQTT Passwort                           |
| `mqtt_topic_prefix` | `ecotracker`                          | Prefix für alle MQTT Topics             |
| `mqtt_qos`          | `0`                                   | MQTT Quality of Service (0, 1, 2)       |
| `mqtt_retain`       | `true`                                | MQTT Retain Flag                        |
| `log_level`         | `info`                                | Log-Level (debug, info, warning, error) |

## Auch als standalone Docker-Container nutzbar

```bash
docker run -d --network host \
  -e ECOTRACKER_URL="http://192.168.44.233/v1/json" \
  -e MQTT_HOST="192.168.44.1" \
  -e POLL_INTERVAL="1" \
  eco2mqtt
```

## Lizenz

MIT
