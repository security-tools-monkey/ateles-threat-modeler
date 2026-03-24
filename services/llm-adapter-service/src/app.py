SERVICE_NAME = "llm-adapter-service"

ROUTES = [
    {"method": "GET", "path": "/health", "handler": "health"},
    {"method": "POST", "path": "/extract", "handler": "extract_nsm_from_image"},
    {"method": "POST", "path": "/classify", "handler": "classify_components"},
    {"method": "POST", "path": "/bind", "handler": "bind_rules"},
    {"method": "POST", "path": "/reason", "handler": "llm_threat_reasoning"},
]

def health():
    return {"status": "ok", "service": SERVICE_NAME}

def extract_nsm_from_image():
    return {"status": "stub", "service": SERVICE_NAME}

def classify_components():
    return {"status": "stub", "service": SERVICE_NAME}

def bind_rules():
    return {"status": "stub", "service": SERVICE_NAME}

def llm_threat_reasoning():
    return {"status": "stub", "service": SERVICE_NAME}

def main():
    print(f"{SERVICE_NAME} stub running")
    print("Routes:")
    for route in ROUTES:
        print(f"  {route['method']} {route['path']} -> {route['handler']}")

if __name__ == "__main__":
    main()
