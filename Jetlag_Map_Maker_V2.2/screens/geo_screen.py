import tkinter as tk
import config

from ui_layout import build_header, build_body
from map_utils import embed_map, make_map_container


def geo_screen(root, show_screen, photo):
    frame = tk.Frame(root, bg=config.BG)

    from screens.main_menu import main_menu

    build_header(
        frame,
        "Geographic Area",
        back_command=lambda: show_screen(main_menu),
        photo=photo
    )

    left, right = build_body(frame, config.BG)

    map_container = make_map_container(right)
    embed_map(map_container, center=config.DEFAULT_MAP_CENTER, zoom=config.DEFAULT_MAP_ZOOM)

    tk.Label(
        left,
        text="Geographic Area (Coming Soon)",
        bg=config.BG,
        fg=config.FG,
        font=config.SUBTITLE_FONT
    ).pack(pady=20)

    tk.Label(
        left,
        text="This screen will let you choose an area by name or region.",
        bg=config.BG,
        fg=config.FG,
        font=config.BODY_FONT,
        wraplength=config.LEFT_PANEL_WIDTH - 20,
        justify="left"
    ).pack(padx=10)

    return frame
