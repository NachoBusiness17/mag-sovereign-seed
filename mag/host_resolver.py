"""DNS-Independent Host Resolver — organ for offline capability.

This organ resolves host services without DNS dependencies, maintaining system
autonomy during network interruptions and Docker restart scenarios.
"""
import json
import os
import socket
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from config import ROOT
except ImportError:
    ROOT = Path(__file__).resolve().parent.parent

STATE_DIR = ROOT / "memory" / "runs" / "host_resolver"
MAPPINGS_FILE = STATE_DIR / "mappings.jsonl"
NETWORK_STATE_FILE = STATE_DIR / "network_state.json"


def resolve_host(service: str, force_fallback: bool = False) -> str:
    """Resolve a host service name to an IP address.
    
    Args:
        service: Service name ('host.docker.internal', 'ollama', 'api_gateway', 'browser_cdp')
        force_fallback: Skip DNS resolution and use fallback
        
    Returns:
        Resolved IP address (e.g., '127.0.0.1')
        
    Raises:
        ValueError: If service cannot be resolved
    """
    # Service definitions with fallback mappings
    service_mappings = {
        'host.docker.internal': {
            'dns': 'host.docker.internal',
            'fallback': '127.0.0.1',
            'port': None
        },
        'ollama': {
            'dns': 'host.docker.internal',
            'fallback': '127.0.0.1',
            'port': 11434
        },
        'api_gateway': {
            'dns': '127.0.0.1',
            'fallback': '127.0.0.1',
            'port': 8001
        },
        'browser_cdp': {
            'dns': '127.0.0.1',
            'fallback': '127.0.0.1',
            'port': 9222
        }
    }
    
    if service not in service_mappings:
        raise ValueError(f"Unknown service: {service}")
    
    mapping = service_mappings[service]
    target = mapping['fallback'] if force_fallback else mapping['dns']
    port = mapping['port']
    
    # Test DNS resolution first (unless forced)
    if not force_fallback and target == 'host.docker.internal':
        if _dns_resolves('host.docker.internal'):
            resolved = 'host.docker.internal'
        else:
            resolved = mapping['fallback']
            _log_resolution(service, target, resolved, "DNS failed, using fallback")
    else:
        resolved = target
        _log_resolution(service, target, resolved, "using fallback")
    
    # Verify service availability if port is specified
    if port:
        host = resolved if resolved != 'host.docker.internal' else '127.0.0.1'
        if not _check_service_availability(host, port):
            raise ValueError(f"Service {service} not available at {host}:{port}")
    
    return resolved


def _dns_resolves(hostname: str) -> bool:
    """Check if hostname resolves via DNS."""
    try:
        socket.gethostbyname(hostname)
        return True
    except socket.gaierror:
        return False


def _check_service_availability(host: str, port: int, timeout: float = 5.0) -> bool:
    """Check if a TCP service is available."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _log_resolution(service: str, target: str, resolved: str, reason: str) -> None:
    """Log resolution event to mappings file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "ts": time.time(),
        "service": service,
        "target": target,
        "resolved": resolved,
        "reason": reason
    }
    
    with open(MAPPINGS_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry) + '\n')


def get_network_state() -> Dict[str, Any]:
    """Get current network connectivity state."""
    return {
        "timestamp": time.time(),
        "host.docker.internal_dns": _dns_resolves('host.docker.internal'),
        "internet_connectivity": _check_service_availability('8.8.8.8', 53, timeout=2.0),
        "services": {
            "ollama": _check_service_availability('127.0.0.1', 11434),
            "api_gateway": _check_service_availability('127.0.0.1', 8001),
            "browser_cdp": _check_service_availability('127.0.0.1', 9222)
        }
    }


def update_network_state() -> Dict[str, Any]:
    """Update network state file."""
    state = get_network_state()
    NETWORK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(NETWORK_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)
    
    return state


def resolve_host_for_service(service_name: str) -> str:
    """Main callable for organ integration."""
    try:
        # Check network state first
        state = get_network_state()
        
        # Force fallback if DNS fails or we're offline
        force_fallback = (
            not state['host.docker.internal_dns'] or
            not state['internet_connectivity']
        )
        
        resolved = resolve_host(service_name, force_fallback=force_fallback)
        
        # Log receipt
        receipt = {
            "ok": True,
            "service": service_name,
            "resolved": resolved,
            "network_state": state,
            "ts": time.time()
        }
        
        return resolved
        
    except Exception as e:
        # Log failure receipt
        receipt = {
            "ok": False,
            "service": service_name,
            "error": str(e),
            "ts": time.time()
        }
        raise


def main() -> None:
    """CLI for testing the resolver."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Host Resolver CLI")
    parser.add_argument("service", nargs='?', default='api_gateway',
                        choices=['host.docker.internal', 'ollama', 'api_gateway', 'browser_cdp'])
    parser.add_argument("--force-fallback", action="store_true")
    parser.add_argument("--update-state", action="store_true")
    
    args = parser.parse_args()
    
    if args.update_state:
        update_network_state()
        print(f"Network state updated: {NETWORK_STATE_FILE}")
    
    try:
        resolved = resolve_host(args.service, args.force_fallback)
        print(f"{args.service} -> {resolved}")
    except Exception as e:
        print(f"Error: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()