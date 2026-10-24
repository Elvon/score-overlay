import json
import urllib.request

TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 score-overlay"


def get_json(url: str, headers: dict | None = None) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))
