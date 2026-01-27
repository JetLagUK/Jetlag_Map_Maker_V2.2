import tkinter as tk
import config

from ui_layout import build_header, build_body
from map_utils import embed_map, make_map_container


def kml_screen(root, show_screen, photo):
    frame = tk.Frame(root, bg=config.BG)

    # Import here to avoid circular imports
    from screens.main_menu import main_menu

    build_header(
        frame,
        "Custom KML Polygon",
        back_command=lambda: show_screen(main_menu),
        photo=photo
    )

    left, right = build_body(frame, config.BG)

    # Map (fixed height container so it doesn't take over)
    map_container = make_map_container(right)
    embed_map(map_container, center=config.DEFAULT_MAP_CENTER, zoom=config.DEFAULT_MAP_ZOOM)

    # Left-side placeholder content
    tk.Label(
        left,
        text="KML Polygon (Coming Soon)",
        bg=config.BG,
        fg=config.FG,
        font=config.SUBTITLE_FONT
    ).pack(pady=(20, 10))

    tk.Label(
        left,
        text="This screen will let you load a KML file and use it as a custom boundary.",
        bg=config.BG,
        fg=config.FG,
        font=config.BODY_FONT,
        wraplength=config.LEFT_PANEL_WIDTH - 20,
        justify="left"
    ).pack(padx=10)

    # Optional button placeholder
    tk.Button(
        left,
        text="Load KML (Coming Soon)",
        bg=config.BTN,
        fg=config.FG,
        width=22,
        state="disabled"
    ).pack(pady=20)

    return frame
