SERVICE_NAME = "ingestion-service"

ROUTES = [
    {"method": "GET", "path": "/health", "handler": "health"},
    {"method": "POST", "path": "/ingest/image", "handler": "ingest_image"},
    {"method": "POST", "path": "/ingest/drawio", "handler": "ingest_drawio"},
]

def health():
    return {"status": "ok", "service": SERVICE_NAME}

def ingest_image():
    return {"status": "stub", "service": SERVICE_NAME}

def ingest_drawio():
    return {"status": "stub", "service": SERVICE_NAME}

def main():
    print(f"{SERVICE_NAME} stub running")
    print("Routes:")
    for route in ROUTES:
        print(f"  {route['method']} {route['path']} -> {route['handler']}")

if __name__ == "__main__":
    main()
