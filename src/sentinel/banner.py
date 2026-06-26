"""ASCII art banners for Sentinel."""

BANNERS = {
    "default": r"""
  ____                  _ _ _
 / ___| ___   __ _  ___| (_) | _____
 \___ \/ _ \ / _` |/ __| | | |/ / _ \
  ___) | (_) | (_| | (__| | |   <  __/
 |____/ \___/ \__, |\___|_|_|_|\_\___|
              |___/
""",
    "shield": r"""
  ╔═══════════════════════════╗
  ║  █ S E N T I N E L █     ║
  ║  ▓ Monitor Everything ▓  ║
  ╚═══════════════════════════╝
""",
    "eye": r"""
     ╭──────────────╮
    ╱   ◉ S E N T I N E L   ◉  ╲
   │   Always Watching. Always.  │
    ╲                            ╱
     ╰──────────────╯
""",
}

BANNER_COLORS = {
    "default": "bold #0E2F76",
    "shield": "#0E2F76",
    "eye": "#22c55e",
}


def get_banner(style="default"):
    return BANNERS.get(style, BANNERS["default"]), BANNER_COLORS.get(style, BANNER_COLORS["default"])
