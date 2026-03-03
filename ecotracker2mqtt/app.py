"""EcoTracker → MQTT Bridge  (Home Assistant Add-on).

Polls the everHome EcoTracker local HTTP API and publishes all values
to MQTT.  When running as an HA add-on the MQTT broker credentials are
auto-detected from the Supervisor API (Mosquitto add-on).  Manual
config via options.json always takes precedence.
"""

import collections
import concurrent.futures
import ipaddress
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time

from flask import Flask, jsonify, Response
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
        "ecotracker_host": os.environ.get("ECOTRACKER_HOST", "192.168.44.233"),
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


# ---------------------------------------------------------------------------
# EcoTracker auto-discovery
# ---------------------------------------------------------------------------

def _get_local_subnets() -> list[ipaddress.IPv4Network]:
    """Detect local subnets via 'ip addr' (works with host_network)."""
    subnets = []
    try:
        result = subprocess.run(
            ["ip", "-o", "-4", "addr", "show"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            # Format: "2: eth0  inet 192.168.44.100/21 brd ..."
            parts = line.split()
            for i, part in enumerate(parts):
                if part == "inet" and i + 1 < len(parts):
                    cidr = parts[i + 1]  # e.g. 192.168.44.100/21
                    try:
                        net = ipaddress.IPv4Network(cidr, strict=False)
                        if not net.is_loopback and net not in subnets:
                            subnets.append(net)
                    except ValueError:
                        pass
    except Exception as exc:
        log.warning("Failed to detect local subnets: %s", exc)
    return subnets


def _probe_ecotracker(ip: str) -> str | None:
    """Check if an IP hosts an EcoTracker. Returns the IP or None."""
    try:
        resp = requests.get(f"http://{ip}/v1/json", timeout=0.8)
        if resp.ok:
            data = resp.json()
            if "power" in data and "energyCounterIn" in data:
                return ip
    except Exception:
        pass
    return None


def _discover_ecotracker() -> str | None:
    """Scan local subnets for an EcoTracker device."""
    subnets = _get_local_subnets()
    log.info("Scanning for EcoTracker on %s ...", ", ".join(str(s) for s in subnets))

    all_ips = []
    for subnet in subnets:
        all_ips.extend(str(ip) for ip in subnet.hosts())

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as pool:
        futures = {pool.submit(_probe_ecotracker, ip): ip for ip in all_ips}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                log.info("EcoTracker found at %s", result)
                # Cancel remaining probes
                for f in futures:
                    f.cancel()
                return result

    log.warning("No EcoTracker found on local network")
    return None



# Supervisor API endpoints – hostname 'supervisor' may not resolve with
# host_network: true, so we fall back to the hard-coded Supervisor IP.
SUPERVISOR_URLS = ["http://supervisor", "http://172.30.32.2"]

# Docker hostnames that don't resolve with host_network and their
# localhost equivalents (Mosquitto add-on also uses host_network).
DOCKER_HOST_MAP = {
    "core-mosquitto": "127.0.0.1",
    "addon_core_mosquitto": "127.0.0.1",
}


def _discover_ha_mqtt() -> dict | None:
    """Try to detect MQTT broker via the HA Supervisor API."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        log.warning("SUPERVISOR_TOKEN not set – MQTT auto-detection unavailable")
        return None

    for base_url in SUPERVISOR_URLS:
        try:
            log.info("Trying MQTT auto-detection via %s …", base_url)
            resp = requests.get(
                f"{base_url}/services/mqtt",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            host = data.get("host", "")
            if not host:
                log.warning("Supervisor returned empty MQTT host")
                return None

            # Map Docker hostnames to IPs reachable with host_network
            resolved = DOCKER_HOST_MAP.get(host, host)
            if resolved != host:
                log.info("Mapped MQTT host %s → %s (host_network)", host, resolved)

            port = int(data.get("port", 1883))
            log.info("Auto-detected MQTT broker at %s:%s", resolved, port)
            return {
                "host": resolved,
                "port": port,
                "user": data.get("username", ""),
                "password": data.get("password", ""),
            }
        except Exception as exc:
            log.warning("MQTT detection via %s failed: %s", base_url, exc)
            continue

    log.warning("All Supervisor endpoints failed – MQTT auto-detection unsuccessful")
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

_host = opts.get("ecotracker_host", "").strip()
if not _host:
    log.info("No ecotracker_host configured – starting auto-discovery …")
    _host = _discover_ecotracker()
    if not _host:
        log.error("EcoTracker not found. Set ecotracker_host in the add-on config.")
        sys.exit(1)
ECOTRACKER_URL = f"http://{_host}/v1/json"
POLL_INTERVAL = float(opts.get("poll_interval", 1))
MQTT_TOPIC_PREFIX = opts.get("mqtt_topic_prefix", "ecotracker")
MQTT_QOS = int(opts.get("mqtt_qos", 0))
MQTT_RETAIN = bool(opts.get("mqtt_retain", True))
HTTP_TIMEOUT = float(opts.get("http_timeout", 5))

# MQTT: manual config takes precedence, then HA auto-detection
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
    log.error("No MQTT broker configured and auto-detection failed. "
              "Set mqtt_host in the add-on config or install the Mosquitto add-on.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# In-memory log buffer for web UI
# ---------------------------------------------------------------------------
LOG_BUFFER: collections.deque = collections.deque(maxlen=500)


class _BufferHandler(logging.Handler):
    """Append formatted log lines to the shared ring buffer."""
    def emit(self, record):
        LOG_BUFFER.append(self.format(record))


_buf_handler = _BufferHandler()
_buf_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
))
logging.getLogger().addHandler(_buf_handler)


# ---------------------------------------------------------------------------
# Flask web UI (ingress) — live log viewer
# ---------------------------------------------------------------------------

LOG_VIEWER_HTML = """\
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EcoTracker Log</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#1a1a1a;color:#d4d4d4;font-family:"SF Mono","Cascadia Mono","JetBrains Mono","Fira Code",Consolas,monospace;font-size:13px;height:100vh;display:flex;flex-direction:column}
#hd{background:#222;padding:10px 16px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #333;flex-shrink:0}
#hd .t{font-size:14px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#e1e1e1}
#hd .st{font-size:11px;color:#666;display:flex;align-items:center;gap:8px}
.dot{width:7px;height:7px;border-radius:50%;background:#555}
.dot.ok{background:#2dd4a0;box-shadow:0 0 6px rgba(45,212,160,.5)}
#log{flex:1;overflow-y:auto;padding:8px 16px;scroll-behavior:auto}
.ln{padding:2px 0;white-space:pre-wrap;word-break:break-all;line-height:1.45}
.ln.e{color:#f06060}
.ln.w{color:#e8a630}
.ln.d{color:#666}
.ln.i{color:#d4d4d4}
#ft{background:#222;padding:6px 16px;font-size:11px;color:#555;border-top:1px solid #333;display:flex;justify-content:space-between;flex-shrink:0}
.ps{color:#e8a630}
</style>
</head>
<body>
<div id="hd"><span class="t">EcoTracker Log</span><span class="st"><span id="cnt">0 lines</span><span id="dt" class="dot"></span></span></div>
<div id="log"></div>
<div id="ft"><span id="si">Auto-scroll aktiv</span><span>1s Refresh</span></div>
<script>
(function(){
var log=document.getElementById("log"),dt=document.getElementById("dt"),
    cnt=document.getElementById("cnt"),si=document.getElementById("si"),
    auto=true,prev=0;
log.addEventListener("scroll",function(){
  var atBottom=log.scrollHeight-log.scrollTop-log.clientHeight<40;
  auto=atBottom;
  si.textContent=auto?"Auto-scroll aktiv":"Auto-scroll pausiert";
  si.className=auto?"":"ps";
});
function cls(l){
  if(l.indexOf("[ERROR]")!==-1)return"e";
  if(l.indexOf("[WARNING]")!==-1)return"w";
  if(l.indexOf("[DEBUG]")!==-1)return"d";
  return"i";
}
function poll(){
  fetch("./api/logs").then(function(r){return r.json()}).then(function(lines){
    dt.classList.add("ok");
    if(lines.length===prev&&prev>0)return;
    prev=lines.length;
    cnt.textContent=lines.length+" lines";
    var html="";
    for(var i=0;i<lines.length;i++){
      html+='<div class="ln '+cls(lines[i])+'">'+lines[i].replace(/</g,"&lt;")+"</div>";
    }
    log.innerHTML=html;
    if(auto)log.scrollTop=log.scrollHeight;
  }).catch(function(){dt.classList.remove("ok")});
}
poll();setInterval(poll,1000);
})();
</script>
</body>
</html>
"""

flask_app = Flask(__name__)
flask_app.logger.setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)


@flask_app.route("/")
def index():
    return Response(LOG_VIEWER_HTML, mimetype="text/html")


@flask_app.route("/api/logs")
def api_logs():
    return jsonify(list(LOG_BUFFER))


def _run_webserver():
    """Run Flask on the ingress port in a daemon thread."""
    flask_app.run(host="0.0.0.0", port=8098, threaded=True)


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
        publish_discovery(client)
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
# HA MQTT Discovery
# ---------------------------------------------------------------------------

DISCOVERY_PREFIX = "homeassistant"

SENSOR_DEFS = [
    {"key": "power",            "name": "Leistung",            "device_class": "power",    "state_class": "measurement",      "unit": "W"},
    {"key": "powerAvg",         "name": "Leistung Durchschnitt", "device_class": "power",    "state_class": "measurement",      "unit": "W"},
    {"key": "powerPhase1",      "name": "Leistung L1",          "device_class": "power",    "state_class": "measurement",      "unit": "W"},
    {"key": "powerPhase2",      "name": "Leistung L2",          "device_class": "power",    "state_class": "measurement",      "unit": "W"},
    {"key": "powerPhase3",      "name": "Leistung L3",          "device_class": "power",    "state_class": "measurement",      "unit": "W"},
    {"key": "energyCounterIn",  "name": "Z\u00e4hler Bezug",         "device_class": "energy",   "state_class": "total_increasing", "unit": "kWh"},
    {"key": "energyCounterOut", "name": "Z\u00e4hler Einspeisung",   "device_class": "energy",   "state_class": "total_increasing", "unit": "kWh"},
    {"key": "agePower",         "name": "Messwert Alter",        "device_class": "duration", "state_class": "measurement",      "unit": "ms",  "entity_category": "diagnostic"},
]


def publish_discovery(client: mqtt.Client):
    """Publish HA MQTT Discovery config for all sensors."""
    device = {
        "identifiers": [f"{MQTT_TOPIC_PREFIX}_ecotracker"],
        "name": "EcoTracker",
        "manufacturer": "everHome",
        "model": "EcoTracker",
    }

    for sensor in SENSOR_DEFS:
        uid = f"{MQTT_TOPIC_PREFIX}_{sensor['key']}"
        payload = {
            "name": sensor["name"],
            "unique_id": uid,
            "state_topic": f"{MQTT_TOPIC_PREFIX}/{sensor['key']}",
            "device_class": sensor["device_class"],
            "state_class": sensor["state_class"],
            "unit_of_measurement": sensor["unit"],
            "device": device,
            "availability_topic": f"{MQTT_TOPIC_PREFIX}/status",
            "payload_available": "online",
            "payload_not_available": "offline",
        }
        if "entity_category" in sensor:
            payload["entity_category"] = sensor["entity_category"]

        topic = f"{DISCOVERY_PREFIX}/sensor/{uid}/config"
        client.publish(topic, payload=json.dumps(payload), qos=1, retain=True)

    log.info("Published HA MQTT Discovery config for %d sensors", len(SENSOR_DEFS))


# ---------------------------------------------------------------------------
# Publish values
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
    log.info("  Web UI         : http://0.0.0.0:8099")

    # Start web UI in background thread
    web_thread = threading.Thread(target=_run_webserver, daemon=True)
    web_thread.start()

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
                log.info(
                    "%+dW (L1:%+d L2:%+d L3:%+d) | Bezug:%.1fkWh Einsp:%.1fkWh",
                    data.get("power", 0),
                    data.get("powerPhase1", 0),
                    data.get("powerPhase2", 0),
                    data.get("powerPhase3", 0),
                    data.get("energyCounterIn", 0),
                    data.get("energyCounterOut", 0),
                )
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
