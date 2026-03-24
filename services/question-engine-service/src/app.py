SERVICE_NAME = "question-engine-service"

ROUTES = [
    {"method": "GET", "path": "/health", "handler": "health"},
    {"method": "POST", "path": "/questions/generate", "handler": "generate_questions"},
]

def health():
    return {"status": "ok", "service": SERVICE_NAME}

def generate_questions():
    return {"status": "stub", "service": SERVICE_NAME}

def main():
    print(f"{SERVICE_NAME} stub running")
    print("Routes:")
    for route in ROUTES:
        print(f"  {route['method']} {route['path']} -> {route['handler']}")

if __name__ == "__main__":
    main()
