SERVICE_NAME = "artifact-store-service"

ROUTES = [
    {"method": "GET", "path": "/health", "handler": "health"},
    {"method": "POST", "path": "/artifacts", "handler": "store_artifact"},
    {"method": "GET", "path": "/artifacts/{id}", "handler": "get_artifact"},
]

def health():
    return {"status": "ok", "service": SERVICE_NAME}

def store_artifact():
    return {"status": "stub", "service": SERVICE_NAME}

def get_artifact():
    return {"status": "stub", "service": SERVICE_NAME}

def main():
    print(f"{SERVICE_NAME} stub running")
    print("Routes:")
    for route in ROUTES:
        print(f"  {route['method']} {route['path']} -> {route['handler']}")

if __name__ == "__main__":
    main()
