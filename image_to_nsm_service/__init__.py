from __future__ import annotations

from pathlib import Path
import pkgutil

# Allow imports from the service's src/ layout when running from repo root.
__path__ = pkgutil.extend_path(__path__, __name__)

_SERVICE_PKG = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "image-to-nsm-service"
    / "src"
    / "image_to_nsm_service"
)
if _SERVICE_PKG.is_dir():
    service_pkg_str = str(_SERVICE_PKG)
    if service_pkg_str not in __path__:
        __path__.append(service_pkg_str)
