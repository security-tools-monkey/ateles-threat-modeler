SERVICE_NAME = "llm-reasoning-service"

ROUTES = [
    {"method": "GET", "path": "/health", "handler": "health"},
    {"method": "POST", "path": "/reason", "handler": "reason_about_threats"},
]

def health():
    return {"status": "ok", "service": SERVICE_NAME}

def reason_about_threats():
    return {"status": "stub", "service": SERVICE_NAME}

def main():
    print(f"{SERVICE_NAME} stub running")
    print("Routes:")
    for route in ROUTES:
        print(f"  {route['method']} {route['path']} -> {route['handler']}")

if __name__ == "__main__":
    main()
