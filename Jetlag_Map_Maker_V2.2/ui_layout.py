import tkinter as tk
import config
from PIL import Image
from image_loader import load_image

def build_header(parent: tk.Widget, title_text: str, back_command, photo=None):
    header = tk.Frame(parent, height=config.HEADER_HEIGHT, bg=config.BG)
    header.pack(fill="x")
    header.pack_propagate(False)

    back_btn = tk.Button(
        header,
        text="← Back",
        bg=config.BTN,
        fg=config.FG,
        command=back_command
    )
    back_btn.grid(row=0, column=0, padx=10, sticky="w")

    title_lbl = tk.Label(
        header,
        text=title_text,
        bg=config.BG,
        fg=config.FG,
        font=config.TITLE_FONT
    )
    title_lbl.grid(row=0, column=1, padx=10)
    if photo:
        # Match logo height to title font size
        font_size = config.TITLE_FONT[1]
        logo_size = (font_size + 20, font_size + 20)

        logo = load_image("logo.png", size=logo_size)
        if logo:
            logo_lbl = tk.Label(header, image=logo, bg=config.BG)
            logo_lbl.image = logo  # keep reference
            logo_lbl.grid(row=0, column=2, padx=10, sticky="e")

    header.grid_columnconfigure(1, weight=1)


def build_body(parent: tk.Widget, bg=None):
    if bg is None:
        bg = config.BG

    body = tk.Frame(parent, bg=bg)
    body.pack(expand=True, fill="both")

    left = tk.Frame(body, bg=bg, width=config.LEFT_PANEL_WIDTH)
    left.pack(side="left", fill="y")
    left.pack_propagate(False)

    right = tk.Frame(body, bg=config.BG)
    right.pack(side="right", expand=True, fill="both")

    return left, right

