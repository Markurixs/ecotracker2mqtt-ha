# ecotracker2mqtt

[![Home Assistant Add-on](https://img.shields.io/badge/Home%20Assistant-Add--on-blue?logo=homeassistant&logoColor=white)](https://github.com/Markurixs/ecotracker2mqtt-ha)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Home Assistant Add-on das den [everHome EcoTracker](https://everhome.cloud) per lokaler HTTP API ausliest und alle Messwerte sekündlich per MQTT bereitstellt.

---

## Features

- Pollt die EcoTracker HTTP API (Standard: jede Sekunde)
- Publiziert jeden Messwert als eigenes MQTT Topic + kompletten JSON-Payload
- Erkennt den Mosquitto Broker Add-on automatisch — keine manuelle MQTT-Konfiguration nötig
- Last-Will Testament: `ecotracker/status` → `offline` bei Verbindungsverlust
- Multi-Arch: amd64, aarch64, armhf, armv7, i386
- Konfigurierbar über die Home Assistant Add-on UI

---

## Installation

1. **Repository hinzufügen**
   - *Einstellungen → Add-ons → Add-on Store → ⋮ (oben rechts) → Repositories*
   - URL eintragen:
     ```
     https://github.com/Markurixs/ecotracker2mqtt-ha
     ```

2. **Add-on installieren**
   - Im Add-on Store erscheint **EcoTracker MQTT Bridge**
   - Installieren und unter *Konfiguration* die IP des EcoTrackers prüfen

3. **Starten**
   - Add-on starten — fertig

> **Tipp:** Wenn der *Mosquitto Broker* Add-on installiert ist, wird der MQTT-Broker automatisch erkannt. `mqtt_host` kann leer bleiben.

---

## MQTT Topics

Alle Werte werden mit Retain-Flag publiziert (konfigurierbar). Der Prefix `ecotracker` ist änderbar.

| Topic | Beschreibung | Beispiel |
| --- | --- | --- |
| `ecotracker/json` | Kompletter JSON-Payload | `{"power":-282, ...}` |
| `ecotracker/power` | Aktuelle Gesamtleistung in Watt | `-282` |
| `ecotracker/powerAvg` | Durchschnittliche Leistung in Watt | `-50` |
| `ecotracker/powerPhase1` | Leistung Phase L1 in Watt | `-904` |
| `ecotracker/powerPhase2` | Leistung Phase L2 in Watt | `370` |
| `ecotracker/powerPhase3` | Leistung Phase L3 in Watt | `251` |
| `ecotracker/energyCounterIn` | Zählerstand Bezug in kWh | `3417631.8` |
| `ecotracker/energyCounterOut` | Zählerstand Einspeisung in kWh | `215770.5` |
| `ecotracker/agePower` | Alter des letzten Messwerts in ms | `500` |
| `ecotracker/status` | Bridge-Status | `online` / `offline` |

> Negative Werte bei `power` = Einspeisung ins Netz

---

## Konfiguration

Alle Optionen sind über die Add-on UI einstellbar:

| Option | Standard | Beschreibung |
| --- | --- | --- |
| `ecotracker_host` | `192.168.44.233` | IP-Adresse oder Hostname des EcoTrackers |
| `poll_interval` | `1` | Abfrageintervall in Sekunden (0.1 – 60) |
| `mqtt_host` | *(leer)* | MQTT Broker IP/Hostname. Leer = automatische Erkennung des Mosquitto Add-ons |
| `mqtt_port` | `1883` | MQTT Broker Port |
| `mqtt_user` | *(leer)* | MQTT Benutzername |
| `mqtt_password` | *(leer)* | MQTT Passwort |
| `mqtt_topic_prefix` | `ecotracker` | Prefix für alle MQTT Topics |
| `mqtt_qos` | `0` | MQTT Quality of Service (0, 1, 2) |
| `mqtt_retain` | `true` | MQTT Retain Flag |
| `log_level` | `info` | Log-Level: `debug`, `info`, `warning`, `error` |

---

## Beispiel: MQTT Sensor in Home Assistant

```yaml
mqtt:
  sensor:
    - name: "Stromverbrauch"
      state_topic: "ecotracker/power"
      unit_of_measurement: "W"
      device_class: power
      state_class: measurement

    - name: "Zählerstand Bezug"
      state_topic: "ecotracker/energyCounterIn"
      unit_of_measurement: "kWh"
      device_class: energy
      state_class: total_increasing

    - name: "Zählerstand Einspeisung"
      state_topic: "ecotracker/energyCounterOut"
      unit_of_measurement: "kWh"
      device_class: energy
      state_class: total_increasing
```

---

## Standalone Docker

Das Add-on funktioniert auch als normaler Docker-Container ohne Home Assistant:

```bash
docker run -d --network host \
  -e ECOTRACKER_HOST="192.168.44.233" \
  -e MQTT_HOST="192.168.44.1" \
  -e POLL_INTERVAL="1" \
  ecotracker-mqtt
```

---

## Lizenz

MIT
