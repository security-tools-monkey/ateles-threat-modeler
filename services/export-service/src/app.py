SERVICE_NAME = "export-service"

ROUTES = [
    {"method": "GET", "path": "/health", "handler": "health"},
    {"method": "POST", "path": "/export/mermaid", "handler": "export_mermaid"},
    {"method": "POST", "path": "/export/graphml", "handler": "export_graphml"},
    {"method": "POST", "path": "/export/xml", "handler": "export_xml"},
    {"method": "POST", "path": "/export/threat-dragon", "handler": "export_threat_dragon"},
]

def health():
    return {"status": "ok", "service": SERVICE_NAME}

def export_mermaid():
    return {"status": "stub", "service": SERVICE_NAME}

def export_graphml():
    return {"status": "stub", "service": SERVICE_NAME}

def export_xml():
    return {"status": "stub", "service": SERVICE_NAME}

def export_threat_dragon():
    return {"status": "stub", "service": SERVICE_NAME}

def main():
    print(f"{SERVICE_NAME} stub running")
    print("Routes:")
    for route in ROUTES:
        print(f"  {route['method']} {route['path']} -> {route['handler']}")

if __name__ == "__main__":
    main()
