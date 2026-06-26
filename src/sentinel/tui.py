"""TUI — Textual-based interactive monitoring dashboard."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)

from .db import CHECK_TYPES, Database, Target, STATUS_OK, STATUS_WARN, STATUS_DOWN
from .checkers import run_check, run_all_checks
from .services import (
    STATUS_ICONS, STATUS_COLORS, CHECK_TYPE_ICONS,
    format_latency, format_uptime,
)

BG = "#07080d"
BG_CARD = "#0E2F76"
BG_CARD2 = "#0a1e50"
ACCENT = "#A9C0E0"
FG = "#e0e8f4"
FG_DIM = "#6b7f9e"
SUCCESS = "#22c55e"
ERROR = "#ef4444"
WARNING = "#fbbf24"


class AddTargetForm(ModalScreen):
    CSS = """
    AddTargetForm { align: center middle; }
    AddTargetForm > Container {
        width: 65; height: auto; max-height: 28;
        background: """ + BG_CARD + """;
        border: thick """ + ACCENT + """;
        padding: 1 2;
    }
    AddTargetForm .form-title {
        text-align: center; margin-bottom: 1;
        color: """ + ACCENT + """;
    }
    AddTargetForm Input, AddTargetForm Select { margin-bottom: 1; }
    AddTargetForm .row { height: auto; }
    AddTargetForm .btn-row { margin-top: 1; height: auto; }
    AddTargetForm Button { margin-right: 1; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        with Container():
            yield Label("Add Target", classes="form-title")
            yield Input(placeholder="Host (e.g. https://example.com)", id="host")
            with Horizontal(classes="row"):
                yield Input(placeholder="Name (optional)", id="name")
                yield Select([(t, t) for t in CHECK_TYPES], id="check_type", value="http")
            with Horizontal(classes="row"):
                yield Input(placeholder="Port (optional)", id="port")
                yield Input(placeholder="Tags (comma-separated)", id="tags")
            with Horizontal(classes="btn-row"):
                yield Button("Add", variant="success", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    @on(Button.Pressed, "#save")
    def save(self):
        host = self.query_one("#host", Input).value.strip()
        if not host:
            return
        name = self.query_one("#name", Input).value.strip() or host
        check_type = self.query_one("#check_type", Select).value or "http"
        port_str = self.query_one("#port", Input).value.strip()
        port = int(port_str) if port_str.isdigit() else None
        tags = self.query_one("#tags", Input).value.strip()

        target = Target(name=name, host=host, port=port, check_type=check_type, tags=tags)
        self.dismiss(target)

    @on(Button.Pressed, "#cancel")
    def cancel(self):
        self.dismiss(None)

    def key_escape(self):
        self.dismiss(None)


class SentinelApp(App):
    CSS = """
    Screen { background: """ + BG + """; }
    #main-container { layout: vertical; height: 100%; }
    #status-bar {
        dock: top; height: auto;
        background: """ + BG_CARD + """;
        border-bottom: solid """ + ACCENT + """;
        padding: 0.5 1;
    }
    #table-container { height: 1fr; }
    DataTable {
        height: 100%; background: """ + BG + """;
    }
    DataTable > .datatable--header {
        background: """ + BG_CARD + """;
        color: """ + ACCENT + """;
    }
    """

    TITLE = "Sentinel"
    SUB_TITLE = "Monitor Everything"

    BINDINGS = [
        Binding("a", "add", "Add", show=True),
        Binding("c", "check", "Check All", show=True),
        Binding("d", "delete", "Delete", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, db_path=None, **kwargs):
        super().__init__(**kwargs)
        self.db = Database(db_path)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main-container"):
            with Horizontal(id="status-bar"):
                yield Label("Loading...", id="stats-label")
            with Vertical(id="table-container"):
                yield DataTable(id="targets-table")
        yield Footer()

    def on_mount(self):
        table = self.query_one("#targets-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Status", "Name", "Type", "Host", "Latency", "Uptime", "Message")
        self.refresh_data()
        self.set_interval(30, self.auto_check)

    def refresh_data(self):
        targets = self.db.list_targets(active_only=True)
        latest = self.db.get_all_latest()
        table = self.query_one("#targets-table", DataTable)
        table.clear()

        ok_count = 0
        warn_count = 0
        down_count = 0

        for t in targets:
            r = latest.get(t.id)
            icon = CHECK_TYPE_ICONS.get(t.check_type, "?")

            if r:
                s_icon = STATUS_ICONS.get(r.status, "\u25cb")
                s_color = STATUS_COLORS.get(r.status, FG_DIM)
                status_str = "{} {}".format(s_icon, r.status.upper())
                latency = format_latency(r.latency_ms)
                uptime = format_uptime(self.db.get_uptime(t.id)) if r else "\u2014"
                msg = r.message[:35]

                if r.status == STATUS_OK:
                    ok_count += 1
                elif r.status == STATUS_WARN:
                    warn_count += 1
                else:
                    down_count += 1

                table.add_row(
                    "[{}]{}[/]".format(s_color, status_str),
                    "{} {}".format(icon, t.name),
                    t.check_type,
                    t.host + (":{}".format(t.port) if t.port else ""),
                    "[{}]{}[/]".format(s_color, latency),
                    "[{}]{}[/]".format(s_color, uptime),
                    msg,
                )
            else:
                down_count += 1
                table.add_row(
                    "[dim]\u25cb UNKNOWN[/]",
                    "{} {}".format(icon, t.name),
                    t.check_type,
                    t.host,
                    "[dim]\u2014[/]",
                    "[dim]\u2014[/]",
                    "[dim]no data[/]",
                )

        # Status bar
        total = len(targets)
        label = self.query_one("#stats-label", Label)
        parts = []
        parts.append("[bold {}]\u25cf {} OK[/]".format(SUCCESS, ok_count))
        if warn_count:
            parts.append("[bold {}]\u25d0 {} WARN[/]".format(WARNING, warn_count))
        if down_count:
            parts.append("[bold {}]\u2716 {} DOWN[/]".format(ERROR, down_count))
        label.update("  {}  •  {} targets total".format("   ".join(parts), total))

    def auto_check(self):
        run_all_checks(self.db)
        self.refresh_data()

    def action_add(self):
        def handle(result):
            if result:
                self.db.add_target(result)
                self.refresh_data()
        self.push_screen(AddTargetForm(), handle)

    def action_delete(self):
        table = self.query_one("#targets-table", DataTable)
        if table.cursor_row is None:
            return
        row = table.get_row_at(table.cursor_row)
        # Extract target name (second column, after icon)
        name_text = row[1]
        # Find target by name
        targets = self.db.list_targets()
        for t in targets:
            tname = "{} {}".format(CHECK_TYPE_ICONS.get(t.check_type, "?"), t.name)
            if tname == name_text or t.name in name_text:
                self.db.remove_target(t.id)
                self.refresh_data()
                return

    def action_check(self):
        run_all_checks(self.db)
        self.refresh_data()

    def action_refresh(self):
        self.refresh_data()

    def on_unmount(self):
        self.db.close()
