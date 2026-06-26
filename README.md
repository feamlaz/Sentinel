# Sentinel

Monitor everything from your terminal.

Sentinel is a multi-target monitoring system that checks the health of your websites, APIs, SSL certificates, DNS records, open ports, and domain expiration dates — all from a single beautiful interface.

## Features

- **5 checker types**: HTTP ping, SSL certificate, DNS resolution, port scan, domain expiry
- **Beautiful TUI dashboard** — live updating, color-coded status grid
- **Web status page** — FastAPI-powered public status dashboard
- **CLI for scripting** — add/check/list/remove from terminal
- **Telegram alerts** — get notified when something goes down
- **Cron mode** — run checks on schedule, auto-alert
- **SQLite storage** — all data local, no cloud dependency
- **Rich history** — track response times, uptime percentage

## Install

```bash
pip install sentinel
```

## Quick Start

```bash
# Add targets
sentinel add https://example.com --type http
sentinel add example.com --type ssl
sentinel add example.com --type dns
sentinel add example.com:443 --type port
sentinel add example.com --type domain

# Run checks
sentinel check

# Launch TUI dashboard
sentinel tui

# Launch web status page
sentinel web

# List all targets
sentinel list
```

## Checker Types

| Type | What it checks | Example |
|------|---------------|---------|
| `http` | HTTP status code, response time | `https://api.example.com/health` |
| `ssl` | Certificate validity, expiry days | `example.com` |
| `dns` | DNS resolution, IP address | `example.com` |
| `port` | TCP port connectivity | `example.com:5432` |
| `domain` | Domain expiration date | `example.com` |

## CLI Reference

| Command | Description |
|---------|-------------|
| `sentinel add` | Add a monitoring target |
| `sentinel list` | List all targets |
| `sentinel remove` | Remove a target |
| `sentinel check` | Run checks on all targets |
| `sentinel dashboard` | Show CLI dashboard |
| `sentinel tui` | Launch interactive TUI |
| `sentinel web` | Launch web status page |
| `sentinel cron` | Run checks on schedule |

## Tech Stack

- **Python 3.9+**
- **Textual** — TUI framework
- **Rich** — terminal formatting
- **FastAPI** — web dashboard
- **httpx** — async HTTP client
- **Click** — CLI framework
- **SQLite** — local storage

## License

MIT
