"""
YadaCoin Open Source License (YOSL) v1.1

Copyright (c) 2017-2025 Matthew Vogel, Reynold Vogel, Inc.
"""

import importlib
import inspect
import json
import re
from typing import Dict, List, Optional, Set, Tuple

from tornado.web import RequestHandler, StaticFileHandler

from yadacoin import version as _version_tuple
from yadacoin.http.base import BaseHandler

_NODE_VERSION = ".".join(str(v) for v in _version_tuple)

HTTP_METHODS = ["get", "post", "put", "delete", "patch"]

TRACKED_PLUGINS = {
    "explorer",
    "keyrisk",
    "keyrotation",
    "yadaaiagent",
    "yadacoinpool",
    "yadanodeinfo",
    "kelutilization",
}


def _regex_to_path(pattern: str) -> str:
    """Convert a Tornado URL regex pattern to an OpenAPI path string."""
    p = pattern.lstrip("^").rstrip("$").rstrip("/") or "/"
    # Named capture groups  (?P<name>...)  →  {name}
    p = re.sub(r"\(\?P<(\w+)>[^)]*\)", r"{\1}", p)
    # Unnamed capture groups  (...)  →  {paramN}
    counter = [0]

    def _unnamed(m):
        counter[0] += 1
        return "{param%d}" % counter[0]

    p = re.sub(r"\([^)]+\)", _unnamed, p)
    # Unescape common metacharacters
    p = p.replace(r"\/", "/").replace(r"\.", ".").replace(r"\-", "-")
    return p or "/"


def _tag_for(path: str, module: str) -> str:
    if "plugins.yadaaiagent" in module or "ai-agent" in path:
        return "AI Agent"
    if "plugins.kelutilization" in module or "kel-utilization" in path:
        return "KEL Utilization"
    if (
        "plugins.keyrotation" in module
        or "key-rotation" in path
        or "derived-key" in path
        or "kel-" in path
    ):
        return "Key Rotation"
    if "plugins.keyrisk" in module or path.startswith("/key-risk"):
        return "Key Risk"
    if "plugins.yadanodeinfo" in module or path.startswith("/node-info"):
        return "Node Info"
    if "plugins.yadacoinpool" in module or path in (
        "/pool",
        "/pool-info",
        "/pool-blocks",
        "/pool-payouts",
        "/market-info",
        "/get-start",
    ):
        return "Pool"
    if "plugins.explorer" in module:
        return "Explorer"
    if (
        "explorer" in module
        or "explorer" in path
        or "holder" in path
        or "hashrate" in path
    ):
        return "Explorer"
    if "node_announce" in module or "announce" in path:
        return "Node Announce"
    if "keyeventlog" in module or path.startswith("/kel"):
        return "Key Event Log"
    if "graph" in module:
        return "Graph"
    if "node" in module and "web" not in module:
        return "Node"
    if "wallet" in module or "wallet" in path or "unwrap" in path:
        return "Wallet"
    if "pool" in module:
        return "Pool (Core)"
    if "product" in module:
        return "Product"
    if "web" in module:
        return "Web"
    return "General"


# ── Source-code introspection helpers ─────────────────────────────────────

# get_argument / get_query_argument / get_body_argument("name", ...)
_RE_GET_ARG = re.compile(
    r'self\.get(?:_query|_body)?_argument\(\s*["\'](\w+)["\'](?:\s*,\s*([^)]+))?',
)
# json_data.get("key") / body.get("key") / post_vars.get("key")
_RE_JSON_GET = re.compile(r'\.get\(\s*["\'](\w+)["\']')
# json.loads(self.request.body) — indicates JSON body
_RE_JSON_BODY = re.compile(r"json\.loads\s*\(\s*self\.request\.body")
# self.render_as_json({...})  — indicates JSON response
_RE_RENDER_JSON = re.compile(r"self\.render_as_json\s*\(")
# common return-value patterns in docstrings: ":return: {...}"
_RE_RETURN_DOC = re.compile(r":returns?:\s*(.+)", re.IGNORECASE)


def _extract_query_params(src: str) -> List[Dict]:
    params = []
    seen: Set[str] = set()
    for m in _RE_GET_ARG.finditer(src):
        name = m.group(1)
        if name in seen:
            continue
        seen.add(name)
        raw_default = (m.group(2) or "").strip()
        # Only truly required when no default argument is present at all
        required = not raw_default
        p: dict = {
            "name": name,
            "in": "query",
            "required": required,
            "schema": {"type": "string"},
        }
        params.append(p)
    return params


def _extract_json_body_schema(src: str) -> Optional[dict]:
    """Return an OpenAPI requestBody schema if the handler reads a JSON body."""
    if not _RE_JSON_BODY.search(src):
        return None
    fields = {}
    for m in _RE_JSON_GET.finditer(src):
        key = m.group(1)
        if key and not key.startswith("_"):
            fields[key] = {"type": "string"}
    schema: dict = {"type": "object"}
    if fields:
        schema["properties"] = fields
    return {
        "required": False,
        "content": {"application/json": {"schema": schema}},
    }


def _extract_response_schema(src: str, doc_lines: List[str]) -> dict:
    """Build a minimal responses dict from source patterns and docstrings."""
    resp_desc = "Success"
    # Pull :return: from docstring
    for line in doc_lines:
        m = _RE_RETURN_DOC.search(line)
        if m:
            resp_desc = m.group(1).strip()
            break

    if _RE_RENDER_JSON.search(src):
        return {
            "200": {
                "description": resp_desc,
                "content": {"application/json": {"schema": {"type": "object"}}},
            }
        }
    return {"200": {"description": resp_desc}}


def _build_openapi_spec() -> dict:
    # ── Core HTTP modules ──────────────────────────────────────────────────
    core_modules = [
        "yadacoin.http.node",
        "yadacoin.http.node_announce",
        "yadacoin.http.graph",
        "yadacoin.http.explorer",
        "yadacoin.http.wallet",
        "yadacoin.http.web",
        "yadacoin.http.pool",
        "yadacoin.http.keyeventlog",
        "yadacoin.http.product",
    ]

    all_handler_tuples: List[Tuple] = []

    for mod_name in core_modules:
        try:
            mod = importlib.import_module(mod_name)
            for attr in dir(mod):
                if attr.endswith("_HANDLERS") or attr == "HANDLERS":
                    value = getattr(mod, attr)
                    if isinstance(value, list):
                        all_handler_tuples.extend(value)
        except Exception:
            pass

    # ── Tracked plugins ────────────────────────────────────────────────────
    for plugin_name in TRACKED_PLUGINS:
        try:
            mod = importlib.import_module(f"plugins.{plugin_name}.handlers")
            handlers = getattr(mod, "HANDLERS", [])
            all_handler_tuples.extend(handlers)
        except Exception:
            pass

    # ── Build OpenAPI paths ────────────────────────────────────────────────
    paths: dict = {}

    for entry in all_handler_tuples:
        if not isinstance(entry, (tuple, list)) or len(entry) < 2:
            continue
        pattern, handler_cls = entry[0], entry[1]
        if not (
            isinstance(handler_cls, type) and issubclass(handler_cls, RequestHandler)
        ):
            continue
        if handler_cls is StaticFileHandler:
            continue

        path = _regex_to_path(pattern)
        module = getattr(handler_cls, "__module__", "")
        tag = _tag_for(path, module)

        path_item: dict = paths.get(path, {})
        for method in HTTP_METHODS:
            if method not in handler_cls.__dict__:
                continue
            func = handler_cls.__dict__[method]
            doc = inspect.getdoc(func) or ""
            doc_lines = [l.strip() for l in doc.splitlines() if l.strip()]
            summary = doc_lines[0] if doc_lines else f"{method.upper()} {path}"

            try:
                src = inspect.getsource(func)
            except Exception:
                src = ""

            op: dict = {
                "summary": summary[:120],
                "operationId": f"{handler_cls.__name__}_{method}",
                "tags": [tag],
                "responses": _extract_response_schema(src, doc_lines),
            }

            if len(doc_lines) > 1:
                op["description"] = "\n".join(doc_lines)

            # Query / path parameters
            q_params = _extract_query_params(src)
            if q_params:
                op["parameters"] = q_params

            # Request body for mutating methods
            if method in ("post", "put", "patch"):
                body_schema = _extract_json_body_schema(src)
                if body_schema:
                    op["requestBody"] = body_schema
                elif not q_params:
                    # No structured body detected; show a generic opaque body note
                    op["requestBody"] = {
                        "required": False,
                        "content": {
                            "application/x-www-form-urlencoded": {
                                "schema": {"type": "object"}
                            }
                        },
                    }

            path_item[method] = op

        if path_item:
            paths[path] = path_item

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "YadaCoin Node API",
            "version": _NODE_VERSION,
            "description": (
                "All HTTP endpoints served by the YadaCoin node core "
                "and its tracked plugins (explorer, keyrotation, yadaaiagent, "
                "yadacoinpool, yadanodeinfo, kelutilization)."
            ),
        },
        "paths": paths,
    }


class ApiDocsHandler(BaseHandler):
    async def get(self):
        html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YadaCoin API Docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
  <style>
    body { margin: 0; }
    .topbar { display: none !important; }
  </style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
  SwaggerUIBundle({
    url: "/api-docs/spec.json",
    dom_id: "#swagger-ui",
    deepLinking: true,
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
    layout: "BaseLayout",
    defaultModelsExpandDepth: -1,
  });
</script>
</body>
</html>"""
        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.finish(html)


class ApiSpecHandler(BaseHandler):
    async def get(self):
        spec = _build_openapi_spec()
        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps(spec, indent=2))


API_DOCS_HANDLERS = [
    (r"/api-docs", ApiDocsHandler),
    (r"/api-docs/spec\.json", ApiSpecHandler),
]
