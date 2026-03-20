import json

def htmx_toast(message: str, type: str = "success", headers: dict = None) -> dict:
    """Helper to append HTMX trigger headers for global toast notification system."""
    if headers is None:
        headers = {}
    
    # Safely merge or create the HX-Trigger JSON
    existing_trigger = headers.get("HX-Trigger", "{}")
    try:
        triggers = json.loads(existing_trigger) if existing_trigger.startswith('{') else {}
    except json.JSONDecodeError:
        triggers = {}
        
    triggers["showMessage"] = {
        "type": type,
        "message": message
    }
    
    headers["HX-Trigger"] = json.dumps(triggers)
    return headers


def is_htmx_request(request) -> bool:
    """Return True if this is an HTMX partial request (HX-Request header present)."""
    return request.headers.get("HX-Request") == "true"
