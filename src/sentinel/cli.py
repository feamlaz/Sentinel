"""CLI interface — click-based command line."""

from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .db import CHECK_TYPES, Database, Target, STATUS_OK, STATUS_WARN, STATUS_DOWN
from .checkers import run_check, run_all_checks
from .services import (
    STATUS_ICONS, STATUS_COLORS, CHECK_TYPE_ICONS,
    format_latency, format_uptime, make_dashboard_panel,
)
from .trends import analyze_trend, TREND_LEVELS
from .banner import get_banner

console = Console()


def _db(ctx):
    return ctx.obj["db"]


@click.group(invoke_without_command=True)
@click.option("--db-path", envvar="SENTINEL_DB", type=click.Path(), default=None, help="Path to database file")
@click.pass_context
def cli(ctx, db_path):
    """Sentinel — monitor everything from your terminal."""
    ctx.ensure_object(dict)
    ctx.obj["db"] = Database(db_path)

    if ctx.invoked_subcommand is None:
        _, color = get_banner("default")
        console.print(r"""
  ____                  _ _ _
 / ___| ___   __ _  ___| (_) | _____
 \___ \/ _ \ / _` |/ __| | | |/ / _ \
  ___) | (_) | (_| | (__| | |   <  __/
 |____/ \___/ \__, |\___|_|_|_|\_\___|
              |___/
        """, style=color, highlight=False)
        console.print("  Monitor everything.\n", style="dim italic")
        db = ctx.obj["db"]
        targets = db.list_targets()
        if targets:
            latest = db.get_all_latest()
            console.print(make_dashboard_panel(targets, latest, db))
        else:
            console.print("  No targets yet. Use [bold]sentinel add[/] to add one.\n", style="dim")


@cli.command()
@click.argument("host")
@click.option("--type", "-t", "check_type", type=click.Choice(CHECK_TYPES), default="http", help="Check type")
@click.option("--name", "-n", default=None, help="Display name (default: host)")
@click.option("--port", "-p", type=int, default=None, help="Port number (for port/ssl checks)")
@click.option("--interval", "-i", type=int, default=300, help="Check interval in seconds")
@click.option("--tags", default="", help="Comma-separated tags")
@click.pass_context
def add(ctx, host, check_type, name, port, interval, tags):
    """Add a monitoring target."""
    db = _db(ctx)
    target = Target(
        name=name or host,
        host=host,
        port=port,
        check_type=check_type,
        interval=interval,
        tags=tags,
    )
    created = db.add_target(target)
    icon = CHECK_TYPE_ICONS.get(check_type, "?")
    console.print("\n  {} [bold green]Added:[/] {} [dim]({})[/]\n".format(icon, created.name, check_type))


@cli.command("list")
@click.option("--all", "show_all", is_flag=True, help="Show inactive targets")
@click.pass_context
def list_targets(ctx, show_all):
    """List all monitoring targets."""
    db = _db(ctx)
    targets = db.list_targets(active_only=not show_all)

    if not targets:
        console.print("\n  [dim]No targets. Use [bold]sentinel add[/] to add one.[/]\n")
        return

    latest = db.get_all_latest()

    table = Table(title="Targets", show_lines=True, border_style="#0E2F76")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Host")
    table.add_column("Status")
    table.add_column("Latency")
    table.add_column("Uptime")
    table.add_column("Message")

    gradient = ["#22c55e", "#4ade80", "#86efac", "#a9c0e0", "#7c6cf0", "#6d72f3"]

    for i, t in enumerate(targets):
        icon = CHECK_TYPE_ICONS.get(t.check_type, "?")
        color = gradient[i % len(gradient)]
        result = latest.get(t.id)
        if result:
            s_icon = STATUS_ICONS.get(result.status, "?")
            s_color = STATUS_COLORS.get(result.status, "white")
            status_str = "[{}]{}[/] {}".format(s_color, s_icon, result.status.upper())
            latency = format_latency(result.latency_ms)
            msg = result.message[:40]
        else:
            status_str = "[dim]—[/]"
            latency = "[dim]—[/]"
            msg = "[dim]no data[/]"

        uptime = format_uptime(db.get_uptime(t.id)) if result else "[dim]—[/]"

        table.add_row(
            str(t.id),
            "{} {}".format(icon, t.name),
            "[{}]{}[/]".format(color, t.check_type),
            t.host + (":{}".format(t.port) if t.port else ""),
            status_str,
            latency,
            uptime,
            msg,
        )

    console.print(table)


@cli.command()
@click.argument("target_id", type=int)
@click.pass_context
def remove(ctx, target_id):
    """Remove a monitoring target."""
    db = _db(ctx)
    target = db.get_target(target_id)
    if not target:
        console.print("\n  [red]Target #{} not found.[/]\n".format(target_id))
        return
    if db.remove_target(target_id):
        console.print("\n  [red]Removed:[/] {}\n".format(target.name))


@cli.command()
@click.option("--target", "-t", "target_id", type=int, default=None, help="Check specific target ID")
@click.pass_context
def check(ctx, target_id):
    """Run health checks."""
    db = _db(ctx)

    if target_id:
        target = db.get_target(target_id)
        if not target:
            console.print("\n  [red]Target #{} not found.[/]\n".format(target_id))
            return
        result = run_check(target)
        db.add_result(result)

        s_icon = STATUS_ICONS.get(result.status, "?")
        s_color = STATUS_COLORS.get(result.status, "white")
        console.print("\n  {} [{}]{}[/] — {} {}".format(
            CHECK_TYPE_ICONS.get(target.check_type, ""),
            s_color, s_icon, target.name, result.message
        ))
        if result.latency_ms is not None:
            console.print("    Latency: {}".format(format_latency(result.latency_ms)))
        console.print()
        return

    # Check all
    results = run_all_checks(db)
    if not results:
        console.print("\n  [dim]No targets to check.[/]\n")
        return

    console.print("\n  [bold]Running checks...[/]\n")
    for target, result in results:
        s_icon = STATUS_ICONS.get(result.status, "?")
        s_color = STATUS_COLORS.get(result.status, "white")
        icon = CHECK_TYPE_ICONS.get(target.check_type, "")

        line = Text()
        line.append("  ")
        line.append(s_icon, style=s_color)
        line.append(" ")
        line.append(target.name, style="bold")
        line.append(" — ")
        line.append(result.message, style=s_color)
        if result.latency_ms is not None:
            line.append(" ({})".format(format_latency(result.latency_ms)), style="dim")
        console.print(line)

        # Trend analysis
        if target.id:
            trend = analyze_trend(db, target.id)
            if trend.get("level") not in ("none", "stable"):
                t_info = TREND_LEVELS.get(trend["level"], {})
                t_color = t_info.get("color", "#6b7280")
                t_icon = t_info.get("icon", "")
                console.print("    {} [{}]Trend: {}[/]".format(t_icon, t_color, trend.get("message", "")))

    console.print()


@cli.command()
@click.pass_context
def dashboard(ctx):
    """Show monitoring dashboard."""
    db = _db(ctx)
    targets = db.list_targets()
    if not targets:
        console.print("\n  [dim]No targets.[/]\n")
        return

    latest = db.get_all_latest()
    console.print(make_dashboard_panel(targets, latest, db))


@cli.command()
@click.pass_context
def tui(ctx):
    """Launch interactive TUI dashboard."""
    from .tui import SentinelApp
    app = SentinelApp(db_path=ctx.obj["db"].db_path)
    app.run()


@cli.command()
@click.option("--host", "-h", default="0.0.0.0", help="Bind host")
@click.option("--port", "-p", type=int, default=8787, help="Bind port")
@click.pass_context
def web(ctx, host, port):
    """Launch web status page."""
    from .web import create_app
    import uvicorn

    app = create_app(db_path=ctx.obj["db"].db_path)
    console.print("\n  [bold #0E2F76]Starting Sentinel web dashboard on http://{}:{}[/]\n".format(host, port))
    uvicorn.run(app, host=host, port=port)


@cli.command()
@click.option("--interval", "-i", type=int, default=300, help="Check interval in seconds")
@click.option("--telegram-token", envvar="SENTINEL_TG_TOKEN", default=None, help="Telegram bot token for alerts")
@click.option("--telegram-chat", envvar="SENTINEL_TG_CHAT", default=None, help="Telegram chat ID for alerts")
@click.pass_context
def cron(ctx, interval, telegram_token, telegram_chat):
    """Run checks on schedule (blocking)."""
    import time
    from .alerts import AlertManager
    from .trends import analyze_trend, should_alert_trend

    db = _db(ctx)
    alert_mgr = AlertManager(telegram_token=telegram_token, telegram_chat=telegram_chat)

    console.print("\n  [bold #0E2F76]Sentinel cron started[/] (interval: {}s)\n".format(interval))

    prev_statuses = {}
    while True:
        results = run_all_checks(db)
        for target, result in results:
            prev = prev_statuses.get(target.id)
            # Alert on status change
            if prev and prev != result.status:
                alert_mgr.send(target, result, prev)
            # Alert on trend degradation
            if target.id and result.status == STATUS_OK:
                trend = analyze_trend(db, target.id)
                if should_alert_trend(trend):
                    alert_mgr.send_trend(target, trend)
            prev_statuses[target.id] = result.status

        now = datetime.now().strftime("%H:%M:%S")
        ok_count = sum(1 for _, r in results if r.status == STATUS_OK)
        total = len(results)
        console.print("  [dim][{}][/dim] Checked {}/{} targets OK [{}]".format(
            now, ok_count, total, "OK" if ok_count == total else "ISSUES"
        ))
        time.sleep(interval)


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
