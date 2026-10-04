import json
import math
import random
import re
import time
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Sequence

import pybase64

DEFAULT_POW_SCRIPT = "https://chatgpt.com/backend-api/sentinel/sdk.js"
CHROME_JS_HEAP_SIZE_LIMIT = 4395630592
_FNV_OFFSET = 2166136261
_FNV_PRIME = 16777619
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
# Page probes: ai, createPRNG, cache, data, solana, dump, InstallTrigger.
_CHROME_FLAGS = (0, 0, 0, 0, 0, 0, 0)
from utils.helper import new_uuid


CORES = [8, 16, 24, 32]
DOCUMENT_KEYS = ["__reactContainer$fzelfjyxej8", "_reactListening5dehydibo78", "location"]
SCREEN_RESOLUTIONS = [[1920, 1080], [1440, 900], [2560, 1440], [3840, 2160]]


class ScriptSrcParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.script_sources: list[str] = []
        self.data_build = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        attrs_dict = dict(attrs)
        src = attrs_dict.get("src")
        if not src:
            return
        self.script_sources.append(src)
        match = re.search(r"c/[^/]*/_", src)
        if match:
            self.data_build = match.group(0)


def parse_pow_resources(html_content: str) -> tuple[list[str], str]:
    parser = ScriptSrcParser()
    parser.feed(html_content)
    script_sources = parser.script_sources or [DEFAULT_POW_SCRIPT]
    data_build = parser.data_build
    if not data_build:
        match = re.search(r'<html[^>]*data-build="([^"]*)"', html_content)
        if match:
            data_build = match.group(1)
    return script_sources, data_build


def _chrome_local_date(moment: datetime | None = None) -> str:
    local = moment.astimezone() if moment is not None else datetime.now().astimezone()
    offset = local.utcoffset()
    total_seconds = int(offset.total_seconds()) if offset is not None else 0
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    if sign == "+" and hours == 8 and minutes == 0:
        tz_name = "中国标准时间"
    else:
        tz_name = local.tzname() or "UTC"
    return (
        f"{_WEEKDAYS[local.weekday()]} {_MONTHS[local.month - 1]} {local.day:02d} {local.year:04d} "
        f"{local.hour:02d}:{local.minute:02d}:{local.second:02d} "
        f"GMT{sign}{hours:02d}{minutes:02d} ({tz_name})"
    )


def _js_time(value: float) -> int | float:
    rounded = round(float(value), 1)
    if rounded.is_integer():
        return int(rounded)
    return rounded


def _js_round(value: float) -> int:
    return int(math.floor(value + 0.5))


def build_pow_config(
    user_agent: str,
    script_sources: Sequence[str] | None = None,
    data_build: str = "",
) -> list[Any]:
    navigator_key = random.choice([
        "registerProtocolHandler−function registerProtocolHandler() { [native code] }",
        "storage−[object StorageManager]",
        "locks−[object LockManager]",
        "appCodeName−Mozilla",
        "permissions−[object Permissions]",
        "share−function share() { [native code] }",
        "webdriver−false",
        "managed−[object NavigatorManagedData]",
        "canShare−function canShare() { [native code] }",
        "vendor−Google Inc.",
        "mediaDevices−[object MediaDevices]",
        "vibrate−function vibrate() { [native code] }",
        "storageBuckets−[object StorageBucketManager]",
        "mediaCapabilities−[object MediaCapabilities]",
        "cookieEnabled−true",
        "virtualKeyboard−[object VirtualKeyboard]",
        "product−Gecko",
        "presentation−[object Presentation]",
        "onLine−true",
        "mimeTypes−[object MimeTypeArray]",
        "credentials−[object CredentialsContainer]",
        "serviceWorker−[object ServiceWorkerContainer]",
        "keyboard−[object Keyboard]",
        "gpu−[object GPU]",
        "doNotTrack",
        "serial−[object Serial]",
        "pdfViewerEnabled−true",
        "language−zh-CN",
        "geolocation−[object Geolocation]",
        "userAgentData−[object NavigatorUAData]",
        "getUserMedia−function getUserMedia() { [native code] }",
        "sendBeacon−function sendBeacon() { [native code] }",
        "hardwareConcurrency−32",
        "windowControlsOverlay−[object WindowControlsOverlay]",
    ])
    window_key = random.choice([
        "0",
        "window",
        "self",
        "document",
        "name",
        "location",
        "customElements",
        "history",
        "navigation",
        "innerWidth",
        "innerHeight",
        "scrollX",
        "scrollY",
        "visualViewport",
        "screenX",
        "screenY",
        "outerWidth",
        "outerHeight",
        "devicePixelRatio",
        "screen",
        "chrome",
        "navigator",
        "onresize",
        "performance",
        "crypto",
        "indexedDB",
        "sessionStorage",
        "localStorage",
        "scheduler",
        "alert",
        "atob",
        "btoa",
        "fetch",
        "matchMedia",
        "postMessage",
        "queueMicrotask",
        "requestAnimationFrame",
        "setInterval",
        "setTimeout",
        "caches",
        "__NEXT_DATA__",
        "__BUILD_MANIFEST",
        "__NEXT_PRELOADREADY",
    ])
    script_source = random.choice(list(script_sources)) if script_sources else DEFAULT_POW_SCRIPT
    page_now = _js_time(random.uniform(400.0, 9000.0))
    time_origin = _js_time((time.time() * 1000) - float(page_now))
    return [
        sum(random.choice(SCREEN_RESOLUTIONS)),
        _chrome_local_date(),
        CHROME_JS_HEAP_SIZE_LIMIT,
        random.random(),
        user_agent,
        script_source,
        data_build,
        "zh-CN",
        "zh-CN,en,zh",
        random.random(),
        navigator_key,
        random.choice(DOCUMENT_KEYS),
        window_key,
        page_now,
        new_uuid(),
        "",
        random.choice(CORES),
        time_origin,
        *_CHROME_FLAGS,
    ]


def _fnv1a_mix(text: str) -> str:
    value = _FNV_OFFSET
    for char in text:
        value ^= ord(char)
        value = (value * _FNV_PRIME) & 0xFFFFFFFF
    value ^= value >> 16
    value = (value * 2246822507) & 0xFFFFFFFF
    value ^= value >> 13
    value = (value * 3266489909) & 0xFFFFFFFF
    value ^= value >> 16
    return f"{value & 0xFFFFFFFF:08x}"


def _config_template(config: Sequence[Any]) -> tuple[str, str, str]:
    head = json.dumps(list(config[:3]), separators=(",", ":"), ensure_ascii=False)
    middle = json.dumps(list(config[4:9]), separators=(",", ":"), ensure_ascii=False)
    tail = json.dumps(list(config[10:]), separators=(",", ":"), ensure_ascii=False)
    return head[:-1] + ",", middle[1:-1] + ",", tail[1:]


def _pow_generate(seed: str, difficulty: str, config: Sequence[Any], limit: int = 500000) -> tuple[str, bool]:
    prefix, middle, suffix = _config_template(config)
    started = time.perf_counter()
    for attempt in range(limit):
        elapsed = _js_round((time.perf_counter() - started) * 1000)
        raw = f"{prefix}{attempt},{middle}{elapsed},{suffix}"
        encoded = pybase64.b64encode(raw.encode("utf-8")).decode("ascii")
        if _fnv1a_mix(seed + encoded)[: len(difficulty)] <= difficulty:
            return encoded + "~S", True
    return "", False


def build_legacy_requirements_token(
    user_agent: str,
    script_sources: Sequence[str] | None = None,
    data_build: str = "",
) -> str:
    config = build_pow_config(user_agent, script_sources=script_sources, data_build=data_build)
    # The page hashes a private Math.random() seed at difficulty "0".
    answer, solved = _pow_generate(str(random.random()), "0", config)
    if not solved:
        raise RuntimeError("failed to solve requirements token")
    return "gAAAAAC" + answer


def build_proof_token(
    seed: str,
    difficulty: str,
    user_agent: str,
    script_sources: Sequence[str] | None = None,
    data_build: str = "",
) -> str:
    config = build_pow_config(user_agent, script_sources=script_sources, data_build=data_build)
    answer, solved = _pow_generate(seed, difficulty, config)
    if not solved:
        raise RuntimeError(f"failed to solve proof token: difficulty={difficulty}")
    return "gAAAAAB" + answer
