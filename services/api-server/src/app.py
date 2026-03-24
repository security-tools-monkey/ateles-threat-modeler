SERVICE_NAME = "api-server"

ROUTES = [
    {"method": "GET", "path": "/health", "handler": "health"},
    {"method": "POST", "path": "/projects", "handler": "create_project"},
    {"method": "POST", "path": "/projects/{id}/runs", "handler": "create_run"},
    {"method": "POST", "path": "/runs/{id}/ingest/image", "handler": "ingest_image"},
    {"method": "POST", "path": "/runs/{id}/ingest/drawio", "handler": "ingest_drawio"},
    {"method": "POST", "path": "/runs/{id}/execute", "handler": "execute_run"},
    {"method": "GET", "path": "/runs/{id}/status", "handler": "get_status"},
    {"method": "GET", "path": "/runs/{id}/nsm", "handler": "get_nsm"},
    {"method": "GET", "path": "/runs/{id}/artifacts", "handler": "list_artifacts"},
    {"method": "GET", "path": "/runs/{id}/findings", "handler": "list_findings"},
    {"method": "GET", "path": "/runs/{id}/questions", "handler": "list_questions"},
    {"method": "GET", "path": "/runs/{id}/exports/{format}", "handler": "get_export"},
]

def health():
    return {"status": "ok", "service": SERVICE_NAME}

def create_project():
    return {"status": "stub", "service": SERVICE_NAME}

def create_run():
    return {"status": "stub", "service": SERVICE_NAME}

def ingest_image():
    return {"status": "stub", "service": SERVICE_NAME}

def ingest_drawio():
    return {"status": "stub", "service": SERVICE_NAME}

def execute_run():
    return {"status": "stub", "service": SERVICE_NAME}

def get_status():
    return {"status": "stub", "service": SERVICE_NAME}

def get_nsm():
    return {"status": "stub", "service": SERVICE_NAME}

def list_artifacts():
    return {"status": "stub", "service": SERVICE_NAME}

def list_findings():
    return {"status": "stub", "service": SERVICE_NAME}

def list_questions():
    return {"status": "stub", "service": SERVICE_NAME}

def get_export():
    return {"status": "stub", "service": SERVICE_NAME}

def main():
    print(f"{SERVICE_NAME} stub running")
    print("Routes:")
    for route in ROUTES:
        print(f"  {route['method']} {route['path']} -> {route['handler']}")

if __name__ == "__main__":
    main()
