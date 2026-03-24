SERVICE_NAME = "nsm-service"

ROUTES = [
    {"method": "GET", "path": "/health", "handler": "health"},
    {"method": "POST", "path": "/nsm", "handler": "create_nsm"},
    {"method": "GET", "path": "/nsm/{id}", "handler": "get_nsm"},
]

def health():
    return {"status": "ok", "service": SERVICE_NAME}

def create_nsm():
    return {"status": "stub", "service": SERVICE_NAME}

def get_nsm():
    return {"status": "stub", "service": SERVICE_NAME}

def main():
    print(f"{SERVICE_NAME} stub running")
    print("Routes:")
    for route in ROUTES:
        print(f"  {route['method']} {route['path']} -> {route['handler']}")

if __name__ == "__main__":
    main()
