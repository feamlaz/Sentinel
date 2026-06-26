"""TUI — Textual-based interactive monitoring dashboard."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
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
from textual.reactive import reactive
from textual.message import Message

from .db import CHECK_TYPES, Database, Target, STATUS_OK, STATUS_WARN, STATUS_DOWN
from .checkers import run_check, run_all_checks
from .services import (
    STATUS_ICONS, STATUS_COLORS, CHECK_TYPE_ICONS,
    format_latency, format_uptime,
)

BG = "#07080d"
BG_CARD = "#0E2F76"
BG_CARD2 = "#0a1e50"
BG_OK = "#081a08"
BG_WARN = "#1a1808"
BG_DOWN = "#1a0808"
ACCENT = "#A9C0E0"
FG = "#e0e8f4"
FG_DIM = "#6b7f9e"
SUCCESS = "#22c55e"
ERROR = "#ef4444"
WARNING = "#fbbf24"


# ── Target Card Widget ─────────────────────────────────────────────────

class TargetCard(Static):
    """A single target status card with pulsing animation."""

    def __init__(self, target_id, name, host, check_type, port=None,
                 status="unknown", latency=None, uptime="", message="",
                 **kwargs):
        super().__init__(**kwargs)
        self.target_id = target_id
        self._name = name
        self._host = host
        self._check_type = check_type
        self._port = port
        self._status = status
        self._latency = latency
        self._uptime = uptime
        self._message = message
        self._pulse_phase = 0
        self._update_display()

    def _update_display(self):
        icon = CHECK_TYPE_ICONS.get(self._check_type, "?")
        s_icon = STATUS_ICONS.get(self._status, "\u25cb")
        s_color = STATUS_COLORS.get(self._status, FG_DIM)

        # Background color based on status
        if self._status == STATUS_OK:
            bg = BG_OK
            status_text = "\u25cf UP"
        elif self._status == STATUS_WARN:
            bg = BG_WARN
            status_text = "\u25d0 WARN"
        elif self._status == STATUS_DOWN:
            bg = BG_DOWN
            status_text = "\u2716 DOWN"
        else:
            bg = BG_CARD2
            status_text = "\u25cb ?"

        latency_str = format_latency(self._latency) if self._latency is not None else "\u2014"

        # Sparkline bar (mini latency bar)
        if self._latency is not None and self._latency > 0:
            bar_len = min(int(self._latency / 30), 30)
            bar_len = max(bar_len, 1)
            bar = "\u2588" * bar_len + "\u2591" * (30 - bar_len)
        else:
            bar = "\u2591" * 30

        host_display = self._host
        if self._port:
            host_display += ":{}".format(self._port)

        self.update(
            "[{s_color}]{s_icon}[/] [bold]{name}[/]  "
            "[dim]{check_type}[/]  [dim]{host}[/]\n"
            "[{s_color}]{status_text}[/]   "
            "[{s_color}]{latency}[/]   "
            "[{accent}]{uptime}[/]\n"
            "[{s_color}]{bar}[/]  [dim]{msg}[/]".format(
                s_color=s_color,
                s_icon=s_icon,
                name=self._name,
                check_type=self._check_type,
                host=host_display,
                status_text=status_text,
                latency=latency_str,
                uptime=self._uptime or "\u2014",
                bar=bar,
                msg=self._message[:40],
                accent=ACCENT,
            )
        )

        # Dynamic border via CSS class
        self.remove_class("status-ok", "status-warn", "status-down", "status-unknown")
        if self._status == STATUS_OK:
            self.add_class("status-ok")
        elif self._status == STATUS_WARN:
            self.add_class("status-warn")
        elif self._status == STATUS_DOWN:
            self.add_class("status-down")
        else:
            self.add_class("status-unknown")

    def update_status(self, status, latency=None, uptime="", message=""):
        self._status = status
        self._latency = latency
        self._uptime = uptime
        self._message = message
        self._update_display()


# ── Add Target Modal ───────────────────────────────────────────────────

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


# ── Main App ───────────────────────────────────────────────────────────

class SentinelApp(App):
    CSS = """
    Screen { background: """ + BG + """; }

    #main-container { layout: vertical; height: 100%; }

    #status-bar {
        dock: top; height: auto;
        background: """ + BG_CARD + """;
        border-bottom: solid """ + ACCENT + """;
        padding: 0.6 1;
    }

    #cards-container {
        height: 1fr;
        overflow-y: auto;
        padding: 0.5;
    }

    TargetCard {
        width: 100%;
        height: auto;
        padding: 0.8 1.2;
        margin: 0.3 0.5;
        border-left: 3px solid """ + FG_DIM + """;
        background: """ + BG_CARD2 + """;
    }

    TargetCard.status-ok {
        border-left-color: """ + SUCCESS + """;
        background: """ + BG_OK + """;
    }

    TargetCard.status-warn {
        border-left-color: """ + WARNING + """;
        background: """ + BG_WARN + """;
    }

    TargetCard.status-down {
        border-left-color: """ + ERROR + """;
        background: """ + BG_DOWN + """;
    }

    /* Pulsing animation for DOWN targets */
    TargetCard.status-down {
        animation: pulse-down 2s infinite;
    }

    @keyframes pulse-down {
        0% { border-left-color: """ + ERROR + """; }
        50% { border-left-color: """ + BG + """; }
        100% { border-left-color: """ + ERROR + """; }
    }

    /* Subtle glow for OK targets */
    TargetCard.status-ok:focus,
    TargetCard.status-ok:hover {
        border-left-color: """ + SUCCESS + """;
        background: #0d2a0d;
    }

    /* Focus highlights */
    TargetCard:focus {
        border-left-size: 1;
        background: """ + BG_CARD + """;
    }

    /* Header bar */
    #header-stats {
        dock: top;
        height: auto;
        background: """ + BG_CARD + """;
        border-bottom: 2px solid """ + ACCENT + """;
        padding: 1 1.5 0.8;
    }

    #header-title {
        color: #fff;
        text-style: bold;
        margin-bottom: 0.3;
    }

    #header-summary {
        color: """ + FG_DIM + """;
    }

    /* Separator line */
    .separator {
        height: 1;
        background: """ + BG_CARD + """;
        margin: 0.3 0.5;
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
        Binding("up", "navigate_up", "Up", show=False),
        Binding("down", "navigate_down", "Down", show=False),
    ]

    def __init__(self, db_path=None, **kwargs):
        super().__init__(**kwargs)
        self.db = Database(db_path)
        self._cards = {}  # target_id -> TargetCard
        self._focus_index = -1

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main-container"):
            with Vertical(id="header-stats"):
                yield Label("\U0001f6e1 SENTINEL \u2014 Monitor Everything", id="header-title")
                yield Label("Loading...", id="header-summary")
            with VerticalScroll(id="cards-container"):
                pass  # Cards will be added dynamically
        yield Footer()

    def on_mount(self):
        self.refresh_data()
        # Auto-check every 30s
        self.set_interval(30, self.auto_check)
        # Pulse refresh every 2s (for animation updates - lightweight)
        self.set_interval(2, self._pulse_refresh)

    def _pulse_refresh(self):
        """Lightweight refresh to update animations without re-checking."""
        # Just refresh the display - the CSS animation handles the pulse
        pass

    def refresh_data(self):
        targets = self.db.list_targets(active_only=True)
        latest = self.db.get_all_latest()

        container = self.query_one("#cards-container", VerticalScroll)
        existing_ids = set(self._cards.keys())
        current_ids = set()

        ok_count = 0
        warn_count = 0
        down_count = 0

        for t in targets:
            current_ids.add(t.id)
            r = latest.get(t.id)

            if r:
                status = r.status
                latency = r.latency_ms
                message = r.message
                uptime = format_uptime(self.db.get_uptime(t.id))

                if status == STATUS_OK:
                    ok_count += 1
                elif status == STATUS_WARN:
                    warn_count += 1
                else:
                    down_count += 1
            else:
                status = "unknown"
                latency = None
                message = "No data"
                uptime = "\u2014"
                down_count += 1

            if t.id in self._cards:
                # Update existing card
                self._cards[t.id].update_status(
                    status=status, latency=latency, uptime=uptime, message=message
                )
            else:
                # Create new card
                card = TargetCard(
                    target_id=t.id,
                    name=t.name,
                    host=t.host,
                    check_type=t.check_type,
                    port=t.port,
                    status=status,
                    latency=latency,
                    uptime=uptime,
                    message=message,
                )
                self._cards[t.id] = card
                container.mount(card)

        # Remove cards for deleted targets
        for tid in existing_ids - current_ids:
            if tid in self._cards:
                self._cards[tid].remove()
                del self._cards[tid]

        # Update header
        label = self.query_one("#header-summary", Label)
        parts = []
        parts.append("[bold {}]\u25cf {} OK[/]".format(SUCCESS, ok_count))
        if warn_count:
            parts.append("[bold {}]\u25d0 {} WARN[/]".format(WARNING, warn_count))
        if down_count:
            parts.append("[bold {}]\u2716 {} DOWN[/]".format(ERROR, down_count))
        total = len(targets)
        label.update("{}  \u2022  {} targets".format("   ".join(parts), total))

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
        # Find focused card
        focused = self.screen.focused
        if isinstance(focused, TargetCard):
            self.db.remove_target(focused.target_id)
            self.refresh_data()

    def action_check(self):
        run_all_checks(self.db)
        self.refresh_data()

    def action_refresh(self):
        self.refresh_data()

    def action_navigate_up(self):
        cards = list(self._cards.values())
        if not cards:
            return
        if self._focus_index > 0:
            self._focus_index -= 1
        elif self._focus_index < 0:
            self._focus_index = len(cards) - 1
        cards[self._focus_index].focus()

    def action_navigate_down(self):
        cards = list(self._cards.values())
        if not cards:
            return
        if self._focus_index < len(cards) - 1:
            self._focus_index += 1
        else:
            self._focus_index = 0
        cards[self._focus_index].focus()

    def on_unmount(self):
        self.db.close()
