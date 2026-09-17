"""Install the versioned image filter through the existing local UI admin API."""

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def configure() -> None:
    base = "http://127.0.0.1:3000/api/v1"
    token = ""
    opener = build_opener(NoRedirect)

    def call(path: str, body: dict[str, object] | None = None) -> dict[str, Any] | None:
        request = Request(
            base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Content-Type": "application/json",
                **({"Authorization": "Bearer " + token} if token else {}),
            },
        )
        try:
            with opener.open(request, timeout=30) as response:
                value = json.load(response)
        except HTTPError as exc:
            if exc.code == 404 and body is None:
                return None
            raise RuntimeError("ui_configuration_http_" + str(exc.code)) from None
        if path == "/functions/list" and isinstance(value, list):
            return {"items": value}
        if not isinstance(value, dict):
            raise RuntimeError("ui_configuration_invalid_response")
        return value

    session = call("/auths/signin", {"email": "admin@localhost", "password": ""})
    if not session or not isinstance(session.get("token"), str):
        raise RuntimeError("ui_configuration_authentication")
    token = session["token"]
    identifier = "atlas_image_references"
    description = "ATLAS M21 managed uploaded-image references"
    source = Path("infra/openwebui_images.py").read_text()
    listing = call("/functions/list")
    if listing is None or not isinstance(listing.get("items"), list):
        raise RuntimeError("ui_configuration_invalid_list")
    exists = any(row.get("id") == identifier for row in listing["items"])
    existing = call("/functions/id/" + identifier) if exists else None
    if existing and existing.get("meta", {}).get("description") != description:
        raise RuntimeError("ui_function_identifier_already_owned")
    if not existing or existing.get("content") != source:
        existing = call(
            "/functions/" + ("id/" + identifier + "/update" if existing else "create"),
            {
                "id": identifier,
                "name": "ATLAS image references",
                "content": source,
                "meta": {"description": description},
            },
        )
    if not existing:
        raise RuntimeError("ui_configuration_missing_function")
    if not existing.get("is_active"):
        call("/functions/id/" + identifier + "/toggle", {})
    if not existing.get("is_global"):
        call("/functions/id/" + identifier + "/toggle/global", {})
