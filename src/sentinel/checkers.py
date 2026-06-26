"""Checkers — HTTP, SSL, DNS, Port, Domain expiry."""

import json
import socket
import ssl
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import httpx

from .db import CheckResult, STATUS_DOWN, STATUS_OK, STATUS_WARN, Target


def check_http(target: Target) -> CheckResult:
    """Check HTTP/HTTPS endpoint — status code and latency."""
    url = target.host
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        start = datetime.now()
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(url)
        latency = (datetime.now() - start).total_seconds() * 1000

        if resp.status_code < 400:
            status = STATUS_OK
            message = "HTTP {}".format(resp.status_code)
        elif resp.status_code < 500:
            status = STATUS_WARN
            message = "HTTP {} (client error)".format(resp.status_code)
        else:
            status = STATUS_DOWN
            message = "HTTP {} (server error)".format(resp.status_code)

        details = json.dumps({
            "status_code": resp.status_code,
            "url": str(resp.url),
            "redirects": len(resp.history),
        })

        return CheckResult(
            target_id=target.id,
            status=status,
            latency_ms=round(latency, 1),
            message=message,
            details=details,
        )

    except httpx.TimeoutException:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="Timeout (15s)")
    except httpx.ConnectError as e:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="Connection failed: {}".format(str(e)[:80]))
    except Exception as e:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="Error: {}".format(str(e)[:80]))


def check_ssl(target: Target) -> CheckResult:
    """Check SSL certificate validity and expiry."""
    host = target.host.replace("https://", "").replace("http://", "").split("/")[0]
    port = target.port or 443

    try:
        start = datetime.now()
        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        latency = (datetime.now() - start).total_seconds() * 1000

        not_after = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
        days_left = (not_after - datetime.now()).days

        # Extract CN safely
        cn = ""
        for field in cert.get("subject", ()):
            for key, val in field:
                if key == "commonName":
                    cn = val
                    break

        # Extract issuer org safely
        issuer_org = ""
        for field in cert.get("issuer", ()):
            for key, val in field:
                if key == "organizationName":
                    issuer_org = val
                    break

        if days_left < 0:
            status = STATUS_DOWN
            message = "Certificate EXPIRED {} days ago".format(abs(days_left))
        elif days_left < 7:
            status = STATUS_DOWN
            message = "Certificate expires in {} days!".format(days_left)
        elif days_left < 30:
            status = STATUS_WARN
            message = "Certificate expires in {} days".format(days_left)
        else:
            status = STATUS_OK
            message = "Certificate valid ({} days left)".format(days_left)

        details = json.dumps({
            "issuer": issuer_org,
            "not_after": not_after.isoformat(),
            "days_left": days_left,
            "cn": cn,
        })

        return CheckResult(
            target_id=target.id,
            status=status,
            latency_ms=round(latency, 1),
            message=message,
            details=details,
        )

    except ssl.SSLError as e:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="SSL error: {}".format(str(e)[:80]))
    except socket.timeout:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="Connection timeout")
    except Exception as e:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="Error: {}".format(str(e)[:80]))


def check_dns(target: Target) -> CheckResult:
    """Check DNS resolution."""
    host = target.host.replace("https://", "").replace("http://", "").split("/")[0]

    try:
        start = datetime.now()
        ips = socket.getaddrinfo(host, None)
        latency = (datetime.now() - start).total_seconds() * 1000

        unique_ips = list(set(addr[4][0] for addr in ips))
        ipv4 = [ip for ip in unique_ips if ":" not in ip]
        ipv6 = [ip for ip in unique_ips if ":" in ip]

        if unique_ips:
            status = STATUS_OK
            message = "Resolved to {} IP{}".format(len(unique_ips), "s" if len(unique_ips) > 1 else "")
        else:
            status = STATUS_DOWN
            message = "No DNS records found"

        details = json.dumps({"ipv4": ipv4[:5], "ipv6": ipv6[:5]})

        return CheckResult(
            target_id=target.id,
            status=status,
            latency_ms=round(latency, 1),
            message=message,
            details=details,
        )

    except socket.gaierror:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="DNS resolution failed")
    except Exception as e:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="Error: {}".format(str(e)[:80]))


def check_port(target: Target) -> CheckResult:
    """Check TCP port connectivity."""
    host = target.host.replace("https://", "").replace("http://", "").split("/")[0]
    port = target.port

    if not port:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="No port specified")

    try:
        start = datetime.now()
        sock = socket.create_connection((host, port), timeout=5)
        latency = (datetime.now() - start).total_seconds() * 1000
        sock.close()

        return CheckResult(
            target_id=target.id,
            status=STATUS_OK,
            latency_ms=round(latency, 1),
            message="Port {} open".format(port),
            details=json.dumps({"port": port}),
        )

    except socket.timeout:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="Port {} timeout".format(port))
    except ConnectionRefusedError:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="Port {} refused".format(port))
    except Exception as e:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="Error: {}".format(str(e)[:80]))


def check_domain(target: Target) -> CheckResult:
    """Check domain expiration using whois-like lookup via socket."""
    host = target.host.replace("https://", "").replace("http://", "").split("/")[0]

    try:
        start = datetime.now()
        # Simple WHOIS query to whois.iana.org
        with socket.create_connection(("whois.iana.org", 43), timeout=10) as sock:
            sock.send((host + "\r\n").encode())
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
        latency = (datetime.now() - start).total_seconds() * 1000

        text = data.decode("utf-8", errors="ignore")

        # Find the refer server
        refer = None
        for line in text.split("\n"):
            if line.lower().startswith("refer:"):
                refer = line.split(":", 1)[1].strip()
                break

        if refer:
            # Query the refer server for actual expiry
            ref_host = refer.split(":")[0]
            ref_port = int(refer.split(":")[1]) if ":" in refer else 43
            with socket.create_connection((ref_host, ref_port), timeout=10) as sock:
                sock.send((host + "\r\n").encode())
                data2 = b""
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    data2 += chunk
            text2 = data2.decode("utf-8", errors="ignore")

            # Look for expiry date
            expiry = None
            for line in text2.split("\n"):
                low = line.lower()
                for keyword in ["registry expiry date", "registrar registration expiration date",
                                "paid-till", "expiry date", "expiration date", "expires"]:
                    if keyword in low:
                        val = line.split(":", 1)[1].strip()
                        try:
                            # Try various date formats
                            for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"]:
                                try:
                                    expiry = datetime.strptime(val[:len(fmt) + 2], fmt)
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass
                        break

            if expiry:
                days_left = (expiry - datetime.now()).days
                if days_left < 0:
                    status = STATUS_DOWN
                    message = "Domain EXPIRED {} days ago".format(abs(days_left))
                elif days_left < 7:
                    status = STATUS_DOWN
                    message = "Domain expires in {} days!".format(days_left)
                elif days_left < 30:
                    status = STATUS_WARN
                    message = "Domain expires in {} days".format(days_left)
                else:
                    status = STATUS_OK
                    message = "Domain valid ({} days left)".format(days_left)

                return CheckResult(
                    target_id=target.id,
                    status=status,
                    latency_ms=round(latency, 1),
                    message=message,
                    details=json.dumps({"expiry": expiry.isoformat(), "days_left": days_left}),
                )

        # Fallback — just resolve
        ips = socket.getaddrinfo(host, None)
        if ips:
            return CheckResult(
                target_id=target.id,
                status=STATUS_OK,
                latency_ms=round(latency, 1),
                message="Domain active (WHOIS expiry not parsed)",
            )
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="Domain not found")

    except Exception as e:
        return CheckResult(target_id=target.id, status=STATUS_DOWN, message="Error: {}".format(str(e)[:80]))


# ── Runner ─────────────────────────────────────────────────────────────

CHECKERS = {
    "http": check_http,
    "ssl": check_ssl,
    "dns": check_dns,
    "port": check_port,
    "domain": check_domain,
}


def run_check(target: Target) -> CheckResult:
    """Run the appropriate checker for a target."""
    checker = CHECKERS.get(target.check_type)
    if not checker:
        return CheckResult(
            target_id=target.id,
            status=STATUS_DOWN,
            message="Unknown check type: {}".format(target.check_type),
        )
    return checker(target)


def run_all_checks(db) -> list:
    """Run checks for all active targets. Returns list of (target, result)."""
    targets = db.list_targets(active_only=True)
    results = []
    for target in targets:
        result = run_check(target)
        db.add_result(result)
        results.append((target, result))
    return results
