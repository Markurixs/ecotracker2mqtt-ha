"""EcoTracker → MQTT Bridge  (Home Assistant Add-on).

Polls the everHome EcoTracker local HTTP API and publishes all values
to MQTT.  When running as an HA add-on the MQTT broker credentials are
auto-discovered from the Supervisor API (Mosquitto add-on).  Manual
config via options.json always takes precedence.
"""

import json
import logging
import os
import signal
import sys
import time

import paho.mqtt.client as mqtt
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OPTIONS_FILE = "/data/options.json"

log = logging.getLogger("ecotracker-mqtt")


def _load_options() -> dict:
    """Load add-on options from /data/options.json (HA) or env vars."""
    if os.path.exists(OPTIONS_FILE):
        with open(OPTIONS_FILE) as fh:
            return json.load(fh)
    # Fallback: plain Docker via env vars
    return {
        "ecotracker_url": os.environ.get("ECOTRACKER_URL", "http://192.168.44.233/v1/json"),
        "poll_interval": float(os.environ.get("POLL_INTERVAL", "1")),
        "mqtt_host": os.environ.get("MQTT_HOST", ""),
        "mqtt_port": int(os.environ.get("MQTT_PORT", "1883")),
        "mqtt_user": os.environ.get("MQTT_USER", ""),
        "mqtt_password": os.environ.get("MQTT_PASS", ""),
        "mqtt_topic_prefix": os.environ.get("MQTT_TOPIC_PREFIX", "ecotracker"),
        "mqtt_qos": int(os.environ.get("MQTT_QOS", "0")),
        "mqtt_retain": os.environ.get("MQTT_RETAIN", "true").lower() == "true",
        "log_level": os.environ.get("LOG_LEVEL", "info"),
    }


def _discover_ha_mqtt() -> dict | None:
    """Try to discover MQTT credentials via the HA Supervisor API."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None
    try:
        resp = requests.get(
            "http://supervisor/services/mqtt",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        if data.get("host"):
            log.info("Auto-discovered HA MQTT service at %s:%s", data["host"], data["port"])
            return {
                "host": data["host"],
                "port": int(data.get("port", 1883)),
                "user": data.get("username", ""),
                "password": data.get("password", ""),
            }
    except Exception as exc:
        log.debug("MQTT auto-discovery failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Build effective config
# ---------------------------------------------------------------------------
opts = _load_options()

# Logging
_level = opts.get("log_level", "info").upper()
logging.basicConfig(
    level=getattr(logging, _level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

ECOTRACKER_URL = opts.get("ecotracker_url", "http://192.168.44.233/v1/json")
POLL_INTERVAL = float(opts.get("poll_interval", 1))
MQTT_TOPIC_PREFIX = opts.get("mqtt_topic_prefix", "ecotracker")
MQTT_QOS = int(opts.get("mqtt_qos", 0))
MQTT_RETAIN = bool(opts.get("mqtt_retain", True))
HTTP_TIMEOUT = float(opts.get("http_timeout", 5))

# MQTT: manual config takes precedence, then HA auto-discovery
MQTT_HOST = opts.get("mqtt_host", "")
MQTT_PORT = int(opts.get("mqtt_port", 1883))
MQTT_USER = opts.get("mqtt_user", "")
MQTT_PASS = opts.get("mqtt_password", "")

if not MQTT_HOST:
    ha_mqtt = _discover_ha_mqtt()
    if ha_mqtt:
        MQTT_HOST = ha_mqtt["host"]
        MQTT_PORT = ha_mqtt["port"]
        MQTT_USER = ha_mqtt["user"]
        MQTT_PASS = ha_mqtt["password"]

if not MQTT_HOST:
    log.error("No MQTT broker configured and auto-discovery failed. "
              "Set mqtt_host in the add-on config or install the Mosquitto add-on.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------
running = True


def _shutdown(signum, _frame):
    global running
    log.info("Received signal %s – shutting down …", signum)
    running = False


signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)

# ---------------------------------------------------------------------------
# MQTT
# ---------------------------------------------------------------------------

def on_connect(client, _userdata, _flags, rc, _properties=None):
    if rc == 0:
        log.info("Connected to MQTT broker %s:%s", MQTT_HOST, MQTT_PORT)
        client.publish(f"{MQTT_TOPIC_PREFIX}/status", payload="online", qos=1, retain=True)
    else:
        log.error("MQTT connection failed (rc=%s)", rc)


def on_disconnect(client, _userdata, rc, _properties=None, _reason=None):
    if rc != 0:
        log.warning("Unexpected MQTT disconnect (rc=%s) – will reconnect", rc)


def create_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(
        client_id="ecotracker-bridge",
        protocol=mqtt.MQTTv311,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.will_set(f"{MQTT_TOPIC_PREFIX}/status", payload="offline", qos=1, retain=True)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    return client


# ---------------------------------------------------------------------------
# EcoTracker polling
# ---------------------------------------------------------------------------
session = requests.Session()
session.headers.update({"Accept": "application/json"})


def poll_ecotracker() -> dict | None:
    try:
        resp = session.get(ECOTRACKER_URL, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        log.warning("EcoTracker request failed: %s", exc)
        return None
    except ValueError as exc:
        log.warning("Invalid JSON from EcoTracker: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

def publish(client: mqtt.Client, data: dict):
    # Full JSON
    client.publish(f"{MQTT_TOPIC_PREFIX}/json", payload=json.dumps(data), qos=MQTT_QOS, retain=MQTT_RETAIN)
    # Individual values
    for key, value in data.items():
        client.publish(f"{MQTT_TOPIC_PREFIX}/{key}", payload=str(value), qos=MQTT_QOS, retain=MQTT_RETAIN)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("EcoTracker MQTT Bridge starting")
    log.info("  EcoTracker URL : %s", ECOTRACKER_URL)
    log.info("  MQTT broker    : %s:%s", MQTT_HOST, MQTT_PORT)
    log.info("  Topic prefix   : %s", MQTT_TOPIC_PREFIX)
    log.info("  Poll interval  : %ss", POLL_INTERVAL)

    client = create_mqtt_client()

    while running:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            break
        except OSError as exc:
            log.error("Cannot connect to MQTT broker: %s – retrying in 5s", exc)
            time.sleep(5)

    client.loop_start()

    try:
        while running:
            t0 = time.monotonic()
            data = poll_ecotracker()
            if data is not None:
                publish(client, data)
                log.debug("Published: %s", data)
            else:
                log.debug("No data this cycle")
            elapsed = time.monotonic() - t0
            sleep_time = max(0, POLL_INTERVAL - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    finally:
        client.publish(f"{MQTT_TOPIC_PREFIX}/status", payload="offline", qos=1, retain=True)
        client.disconnect()
        client.loop_stop()
        log.info("Shutdown complete")


if __name__ == "__main__":
    main()
