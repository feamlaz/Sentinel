<div align="center">

<br>

# 🛡️ SENTINEL

**Monitor everything from your terminal.**

Checks your websites, APIs, SSL certs, DNS, ports, and domains —  
all from one beautiful interface.

<br>

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-0E2F76?style=for-the-badge&logo=python&logoColor=A9C0E0)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-0E2F76?style=for-the-badge&logoColor=A9C0E0)](LICENSE)
[![SQLite](https://img.shields.io/badge/SQLite-local-0E2F76?style=for-the-badge&logo=sqlite&logoColor=A9C0E0)](https://sqlite.org)

<br>

</div>

---

## ✨ What it does

<table>
<tr>
<td width="50%">

### 🌐 HTTP Ping
Hit any URL, check status codes & response times. Redirects followed automatically.

</td>
<td width="50%">

### 🔒 SSL Certificates
Check cert validity, days until expiry. Warns before it's too late.

</td>
</tr>
<tr>
<td width="50%">

### 📍 DNS Resolution
Verify DNS records resolve correctly. See all IPv4 & IPv6 addresses.

</td>
<td width="50%">

### 🔌 Port Scanning
Test TCP port connectivity. Database, SSH, custom services — anything.

</td>
</tr>
<tr>
<td width="50%">

### 🏠 Domain Expiry
Track domain registration expiration. Never lose a domain again.

</td>
<td width="50%">

### 📈 Trend Analysis
Detect latency degradation **before** it causes downtime. Smart alerts when things get slow.

</td>
</tr>
</table>

---

## 🚀 Quick Start

```bash
pip install sentinel
```

```bash
# Add targets
sentinel add https://example.com --type http
sentinel add example.com --type ssl
sentinel add example.com --type dns
sentinel add example.com:5432 --type port
sentinel add example.com --type domain

# Run checks
sentinel check

# Launch TUI
sentinel tui

# Launch web dashboard
sentinel web
```

---

## 🖥️ Interfaces

<table>
<tr>
<th>CLI</th>
<th>TUI</th>
<th>Web</th>
</tr>
<tr>
<td>

```bash
sentinel check
```

Rich terminal output with  
colored status icons,  
latency bars, and  
trend warnings.

</td>
<td>

```bash
sentinel tui
```

Interactive Textual dashboard.  
Live-updating every 30s.  
Add/delete targets in-app.

</td>
<td>

```bash
sentinel web
```

Beautiful FastAPI status page.  
Sparkline charts, trend badges,  
auto-refresh every 60s.

</td>
</tr>
</table>

---

## 📊 Web Dashboard

Dark theme status page with real-time data:

- **Sparkline charts** — 24h latency history per target
- **Trend badges** — RISING / SPIKING / DEGRADING warnings
- **Uptime percentage** — calculated from check history
- **Auto-refresh** — updates every 60 seconds
- **API endpoints** — `/api/status`, `/api/history/{id}`, `/api/trend/{id}`

---

## 🔔 Alerts

Get notified when things go wrong — **or before they do**:

| Alert type | When it triggers |
|---|---|
| Status change | Target goes UP → DOWN or DOWN → UP |
| Trend: Rising | Latency grew >25% over 2 hours |
| Trend: Spiking | Latency peaked at 3x baseline |
| Trend: Degrading | Error rate exceeds 30% |

**Telegram** alerts out of the box:

```bash
sentinel cron \
  --telegram-token "123456:ABC" \
  --telegram-chat "-1001234567890"
```

Or use environment variables: `SENTINEL_TG_TOKEN` and `SENTINEL_TG_CHAT`.

---

## ⌨️ CLI Reference

| Command | Description |
|---------|-------------|
| `sentinel` | Show dashboard |
| `sentinel add HOST` | Add a monitoring target |
| `sentinel list` | List all targets |
| `sentinel remove ID` | Remove a target |
| `sentinel check` | Run health checks |
| `sentinel check -t ID` | Check specific target |
| `sentinel dashboard` | CLI dashboard panel |
| `sentinel tui` | Launch interactive TUI |
| `sentinel web` | Launch web status page |
| `sentinel cron` | Scheduled checks + alerts |

### Add target options

```
sentinel add HOST [--type TYPE] [--name NAME] [--port PORT] [--interval SECS] [--tags TAGS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | `http` | Check type: `http`, `ssl`, `dns`, `port`, `domain` |
| `--name` | host | Display name |
| `--port` | — | Port number (for port/ssl checks) |
| `--interval` | `300` | Check interval in seconds |
| `--tags` | — | Comma-separated tags |

---

## 🏗️ Architecture

```
sentinel/
├── cli.py          Click CLI — all commands
├── db.py           SQLite — targets + results + aggregations
├── checkers.py     5 checkers — HTTP, SSL, DNS, Port, Domain
├── trends.py       Trend analysis — detect latency degradation
├── alerts.py       Telegram alerts + trend notifications
├── services.py     Formatting helpers, dashboard panel builder
├── banner.py       ASCII art banners
├── tui.py          Textual TUI — interactive dashboard
├── web.py          FastAPI web dashboard
└── templates/
    └── dashboard.html   Jinja2 template + Canvas sparklines
```

---

## 🛠️ Tech Stack

<div align="center">

| Category | Technology |
|----------|-----------|
| Language | ![Python](https://img.shields.io/badge/Python-3.9+-0E2F76?style=flat-square&logo=python&logoColor=A9C0E0) |
| CLI | ![Click](https://img.shields.io/badge/Click-8.1-0E2F76?style=flat-square&logoColor=A9C0E0) |
| Terminal UI | ![Textual](https://img.shields.io/badge/Textual-3.0-0E2F76?style=flat-square&logoColor=A9C0E0) |
| Terminal formatting | ![Rich](https://img.shields.io/badge/Rich-13+-0E2F76?style=flat-square&logoColor=A9C0E0) |
| Web framework | ![FastAPI](https://img.shields.io/badge/FastAPI-0.111-0E2F76?style=flat-square&logo=fastapi&logoColor=A9C0E0) |
| HTTP client | ![httpx](https://img.shields.io/badge/httpx-0.27-0E2F76?style=flat-square&logoColor=A9C0E0) |
| Templates | ![Jinja2](https://img.shields.io/badge/Jinja2-3.1-0E2F76?style=flat-square&logoColor=A9C0E0) |
| Storage | ![SQLite](https://img.shields.io/badge/SQLite-local-0E2F76?style=flat-square&logo=sqlite&logoColor=A9C0E0) |

</div>

---

## 📄 License

[MIT](LICENSE) — use it however you want.

<br>

<div align="center">

*Built with 🖤 by [nomer](https://github.com/Feamlaz)*

</div>
