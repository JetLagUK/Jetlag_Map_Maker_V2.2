import tkinter as tk
import config
from image_loader import load_image
from ui_layout import build_header, build_body
from map_utils import embed_map, make_map_container
from osm_fetcher import fetch_osm_data
import math
import pandas as pd
import simplekml
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox


def bbox_screen(root, show_screen, photo):
    frame = tk.Frame(root, bg=config.BG)

    # Store BOTH: map objects + exportable data
    hide_zone_shapes = []  # drawn map objects (tkintermapview path/polygon objects)
    hide_zone_data = []    # list of (lat, lon, radius_m) for KML export

    # Local import avoids circular imports
    from screens.main_menu import main_menu

    build_header(
        frame,
        "Bounding Box",
        back_command=lambda: show_screen(main_menu),
        photo=photo
    )

    left, right = build_body(frame, config.BG)

    # ---- Map ----
    map_container = make_map_container(right)   # padded + expands
    map_widget = embed_map(map_container)

    # --- Marker icons (adjust filenames to match your assets folder) ---
    ICON_SIZE = (28, 28)
    icons = {
        "Train": load_image("train.png", size=ICON_SIZE),
        "Tram": load_image("tram.png", size=ICON_SIZE),
        "Bus": load_image("bus.png", size=ICON_SIZE),
        "Subway": load_image("subway.png", size=ICON_SIZE),
    }
    TRANSPARENT_ICON = tk.PhotoImage(width=1, height=1)

    # Keep track of drawn items so we can delete/replace them
    bbox_shape = {"obj": None}

    # Track markers per type so re-fetch replaces them
    markers_by_type = {"Train": [], "Tram": [], "Bus": [], "Subway": []}

    # One text label on the map at a time (deferred updates to avoid freezes)
    label_marker = {"obj": None}
    _label_after_id = {"id": None}

    def _delete_label_marker():
        if label_marker["obj"] is not None:
            try:
                label_marker["obj"].delete()
            except Exception:
                pass
            label_marker["obj"] = None

    def schedule_clear_label():
        if _label_after_id["id"] is not None:
            try:
                root.after_cancel(_label_after_id["id"])
            except Exception:
                pass
            _label_after_id["id"] = None

        _label_after_id["id"] = root.after(0, _delete_label_marker)

    def schedule_show_label(lat, lon, name):
        if _label_after_id["id"] is not None:
            try:
                root.after_cancel(_label_after_id["id"])
            except Exception:
                pass
            _label_after_id["id"] = None

        def _apply():
            _delete_label_marker()
            lat_offset = 0.00035
            label_marker["obj"] = map_widget.set_marker(
                float(lat) + lat_offset,
                float(lon),
                text=name,
                icon=TRANSPARENT_ICON,
                icon_anchor="center"
            )

        _label_after_id["id"] = root.after(0, _apply)

    # Clicking empty map clears label
    if hasattr(map_widget, "add_left_click_map_command"):
        map_widget.add_left_click_map_command(lambda _coords: schedule_clear_label())

    def clear_markers(type_name):
        for m in markers_by_type.get(type_name, []):
            try:
                m.delete()
            except Exception:
                pass
        markers_by_type[type_name] = []

    def make_marker_click(lat, lon, name):
        def _handler(*_args, **_kwargs):
            schedule_show_label(lat, lon, name)
        return _handler

    def plot_points(type_name, df, limit=500):
        clear_markers(type_name)

        if df is None or df.empty:
            return

        icon = icons.get(type_name)

        count = 0
        for row in df.itertuples(index=False):
            on_click = make_marker_click(row.Latitude, row.Longitude, row.Name)

            try:
                marker = map_widget.set_marker(
                    row.Latitude,
                    row.Longitude,
                    icon=icon,
                    icon_anchor="center",
                    command=on_click
                )
            except TypeError:
                marker = map_widget.set_marker(
                    row.Latitude,
                    row.Longitude,
                    icon=icon,
                    command=on_click
                )

            markers_by_type[type_name].append(marker)
            count += 1
            if count >= limit:
                break

    def haversine_m(lat1, lon1, lat2, lon2):
        """Distance in meters."""
        R = 6371000.0
        p1 = math.radians(lat1)
        p2 = math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)

        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def deduplicate_all_by_priority(threshold_m):
        if threshold_m <= 0:
            return {"Train": 0, "Subway": 0, "Tram": 0, "Bus": 0}, 0

        priority_keep_order = ["Train", "Subway", "Tram", "Bus"]

        dfs = [config.all_data.get(t) for t in priority_keep_order]
        dfs = [d for d in dfs if d is not None and not d.empty]
        if not dfs:
            return {"Train": 0, "Subway": 0, "Tram": 0, "Bus": 0}, 0

        all_concat = pd.concat(dfs, ignore_index=True)
        mean_lat = float(all_concat["Latitude"].mean())

        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * math.cos(math.radians(mean_lat))
        cell_size_m = float(threshold_m)

        def cell_key(lat, lon):
            x = lon * m_per_deg_lon
            y = lat * m_per_deg_lat
            return (int(x // cell_size_m), int(y // cell_size_m))

        kept_points = []
        grid = {}

        def too_close_to_kept(lat, lon):
            cx, cy = cell_key(lat, lon)
            for nx in (cx - 1, cx, cx + 1):
                for ny in (cy - 1, cy, cy + 1):
                    for kp_i in grid.get((nx, ny), []):
                        klat, klon = kept_points[kp_i]
                        if haversine_m(lat, lon, klat, klon) <= threshold_m:
                            return True
            return False

        def add_kept(lat, lon):
            cx, cy = cell_key(lat, lon)
            kept_points.append((lat, lon))
            idx = len(kept_points) - 1
            grid.setdefault((cx, cy), []).append(idx)

        removed_counts = {"Train": 0, "Subway": 0, "Tram": 0, "Bus": 0}

        for t in priority_keep_order:
            df = config.all_data.get(t)
            if df is None or df.empty:
                continue

            keep_rows = []
            df2 = df.reset_index(drop=True)

            for i, row in df2.iterrows():
                lat = float(row["Latitude"])
                lon = float(row["Longitude"])

                if too_close_to_kept(lat, lon):
                    removed_counts[t] += 1
                    continue

                keep_rows.append(i)
                add_kept(lat, lon)

            config.all_data[t] = df2.iloc[keep_rows].reset_index(drop=True)

        total_removed = sum(removed_counts.values())
        return removed_counts, total_removed

    def fetch_and_plot(osm_filter, type_name, status_label):
        df = fetch_osm_data(osm_filter, type_name, status_label, point1_entry, point2_entry)
        if df is not None and not df.empty:
            plot_points(type_name, df)

    # ---- Hiding zones helpers ----
    def clear_hiding_zones():
        for obj in hide_zone_shapes:
            try:
                obj.delete()
            except Exception:
                pass
        hide_zone_shapes.clear()
        hide_zone_data.clear()

    def circle_points(lat, lon, radius_m, segments=36):
        if radius_m <= 0:
            return []
        lat = float(lat)
        lon = float(lon)

        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))
        if m_per_deg_lon == 0:
            return []

        dlat = radius_m / m_per_deg_lat
        dlon = radius_m / m_per_deg_lon

        pts = []
        for i in range(segments + 1):
            a = 2 * math.pi * i / segments
            pts.append((lat + dlat * math.sin(a), lon + dlon * math.cos(a)))
        return pts

    def draw_hiding_zone(lat, lon, radius_m):
        if radius_m <= 200:
            seg = 18
        elif radius_m <= 600:
            seg = 24
        else:
            seg = 32

        pts = circle_points(lat, lon, radius_m, segments=seg)
        if not pts:
            return None

        if hasattr(map_widget, "set_path"):
            return map_widget.set_path(pts, width=1)
        elif hasattr(map_widget, "set_polygon"):
            return map_widget.set_polygon(pts, border_width=1)
        return None

    def save_to_kml():
        path = filedialog.asksaveasfilename(
            defaultextension=".kml",
            filetypes=[("KML files", "*.kml")],
            title="Save game area"
        )
        if not path:
            return

        kml = simplekml.Kml()

        # Single folder only (My Maps friendly)
        game_folder = kml.newfolder(name="Game area")

        # ---- Stops (flat) ----
        for t in ("Train", "Subway", "Tram", "Bus"):
            df = config.all_data.get(t)
            if df is None or df.empty:
                continue

            for row in df.itertuples(index=False):
                name = getattr(row, "Name", "Unnamed") or "Unnamed"
                lat = float(row.Latitude)
                lon = float(row.Longitude)

                p = game_folder.newpoint(
                    name=f"{t}: {name}",
                    coords=[(lon, lat)]
                )
                p.description = f"Type: {t}"

        # ---- Hiding zones (flat) ----
        for i, (lat, lon, radius_m) in enumerate(hide_zone_data, start=1):
            pts = circle_points(lat, lon, radius_m, segments=36)
            if not pts:
                continue

            ring = [(lo, la) for la, lo in pts]
            if ring[0] != ring[-1]:
                ring.append(ring[0])

            pol = game_folder.newpolygon(name=f"Hiding zone {i} ({int(radius_m)}m)")
            pol.outerboundaryis = ring
            pol.tessellate = 1

            # My Maps more reliably shows polygons when they have light fill
            pol.style.linestyle.width = 1
            pol.style.linestyle.color = simplekml.Color.red
            pol.style.polystyle.fill = 1
            pol.style.polystyle.color = simplekml.Color.changealphaint(60, simplekml.Color.red)

        kml.save(path)
        messagebox.showinfo("Export complete", f"Saved:\n{path}")

    # ---- Inputs ----
    tk.Label(
        left,
        text="Bounding Box",
        bg=config.BG,
        fg=config.FG,
        font=config.SUBTITLE_FONT
    ).grid(row=0, column=0, columnspan=2, pady=(10, 10))

    tk.Label(left, text="Point 1 (lat, lon):", bg=config.BG, fg=config.FG)\
        .grid(row=1, column=0, sticky="e", pady=2, padx=(0, 6))
    point1_entry = tk.Entry(left, width=25)
    point1_entry.grid(row=1, column=1, pady=2)

    tk.Label(left, text="Point 2 (lat, lon):", bg=config.BG, fg=config.FG)\
        .grid(row=2, column=0, sticky="e", pady=2, padx=(0, 6))
    point2_entry = tk.Entry(left, width=25)
    point2_entry.grid(row=2, column=1, pady=2)

    # ---- Set Bounding Box button ----
    def _delete_shape(obj):
        if obj is None:
            return
        try:
            obj.delete()
        except Exception:
            pass

    def set_bounding_box():
        try:
            lat1, lon1 = map(float, point1_entry.get().split(","))
            lat2, lon2 = map(float, point2_entry.get().split(","))

            south = min(lat1, lat2)
            north = max(lat1, lat2)
            west = min(lon1, lon2)
            east = max(lon1, lon2)
        except Exception:
            return

        config.bound_box = [south, west, north, east]

        for ent in (point1_entry, point2_entry):
            ent.config(
                state="disabled",
                disabledforeground=config.FG,
                disabledbackground=config.BG,
                relief="flat"
            )

        if hasattr(map_widget, "fit_bounding_box"):
            map_widget.fit_bounding_box((north, west), (south, east))
        else:
            map_widget.set_position((south + north) / 2, (west + east) / 2)
            map_widget.set_zoom(config.DEFAULT_MAP_ZOOM)

        corners = [
            (north, west),
            (north, east),
            (south, east),
            (south, west),
            (north, west)
        ]

        _delete_shape(bbox_shape["obj"])
        bbox_shape["obj"] = None

        if hasattr(map_widget, "set_path"):
            bbox_shape["obj"] = map_widget.set_path(corners)
        elif hasattr(map_widget, "set_polygon"):
            bbox_shape["obj"] = map_widget.set_polygon(corners)

        set_bbox_btn.config(state="disabled", text="Bounding Box Set")

    set_bbox_btn = tk.Button(
        left,
        text="Set Bounding Box",
        bg=config.BTN,
        fg=config.FG,
        width=22,
        command=set_bounding_box
    )
    set_bbox_btn.grid(row=3, column=0, columnspan=2, pady=(10, 5))

    # ---- Fetch Buttons (2x2 grid) ----
    fetch_frame = tk.Frame(left, bg=config.BG)
    fetch_frame.grid(row=4, column=0, columnspan=2, pady=15)

    buttons = [
        ("Fetch Train", 'railway=station][station!=subway', "Train"),
        ("Fetch Tram", 'railway=tram_stop', "Tram"),
        ("Fetch Bus", 'highway=bus_stop', "Bus"),
        ("Fetch Subway", 'station=subway', "Subway"),
    ]

    for i, (text, osm_filter, type_name) in enumerate(buttons):
        r = (i // 2) * 2
        c = i % 2

        status = tk.Label(
            fetch_frame,
            text="",
            bg=config.BG,
            fg=config.FG,
            wraplength=180,
            justify="left",
            anchor="w"
        )

        tk.Button(
            fetch_frame,
            text=text,
            width=15,
            bg=config.BTN,
            fg=config.FG,
            command=lambda f=osm_filter, t=type_name, l=status: fetch_and_plot(f, t, l)
        ).grid(row=r, column=c, padx=6, pady=4)

        status.grid(row=r + 1, column=c, padx=6, pady=(0, 10), sticky="w")

    fetch_frame.grid_columnconfigure(0, weight=1)
    fetch_frame.grid_columnconfigure(1, weight=1)

    def run_dedup():
        threshold = int(dedup_slider.get())
        deduplicate_all_by_priority(threshold)

        for t in ("Train", "Subway", "Tram", "Bus"):
            df = config.all_data.get(t)
            if df is not None and not df.empty:
                plot_points(t, df)
            else:
                clear_markers(t)

        dedup_value_label.config(text=f"{threshold} m")

    # ---- Dedup controls ----
    dedup_frame = tk.Frame(left, bg=config.BG)
    dedup_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=(5, 8))

    tk.Label(
        dedup_frame,
        text="Deduplicate distance (m):",
        bg=config.BG,
        fg=config.FG,
        font=config.BODY_FONT
    ).grid(row=0, column=0, columnspan=3, sticky="w")

    dedup_value_label = tk.Label(
        dedup_frame,
        text="0 m",
        bg=config.BG,
        fg=config.FG,
        width=6,
        anchor="w"
    )
    dedup_value_label.grid(row=1, column=1, sticky="w", padx=(6, 6))

    def on_slider_change(val):
        dedup_value_label.config(text=f"{int(float(val))} m")

    dedup_slider = tk.Scale(
        dedup_frame,
        from_=0,
        to=1000,
        resolution=100,
        orient="horizontal",
        length=170,
        showvalue=False,
        bg=config.BG,
        fg=config.FG,
        highlightthickness=0,
        troughcolor="#2A3B57",
        command=on_slider_change
    )
    dedup_slider.grid(row=1, column=0, sticky="ew")

    dedup_btn = tk.Button(
        dedup_frame,
        text="Deduplicate",
        bg=config.BTN,
        fg=config.FG,
        width=12,
        command=run_dedup
    )
    dedup_btn.grid(row=1, column=2, sticky="e")

    dedup_frame.grid_columnconfigure(0, weight=1)

    def create_hiding_zones():
        radius_m = int(hide_slider.get())
        clear_hiding_zones()

        if radius_m <= 0:
            return

        for t in ("Train", "Subway", "Tram", "Bus"):
            df = config.all_data.get(t)
            if df is None or df.empty:
                continue

            for row in df.itertuples(index=False):
                lat = float(row.Latitude)
                lon = float(row.Longitude)

                obj = draw_hiding_zone(lat, lon, radius_m)
                if obj is not None:
                    hide_zone_shapes.append(obj)
                    hide_zone_data.append((lat, lon, radius_m))

    # ---- Hiding Zone controls ----
    hide_frame = tk.Frame(left, bg=config.BG)
    hide_frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))

    tk.Label(
        hide_frame,
        text="Hiding zone radius (m):",
        bg=config.BG,
        fg=config.FG,
        font=config.BODY_FONT
    ).grid(row=0, column=0, columnspan=3, sticky="w")

    hide_value_label = tk.Label(
        hide_frame,
        text="0 m",
        bg=config.BG,
        fg=config.FG,
        width=6,
        anchor="w"
    )
    hide_value_label.grid(row=1, column=1, sticky="w", padx=(6, 6))

    def on_hide_slider(val):
        hide_value_label.config(text=f"{int(float(val))} m")

    hide_slider = tk.Scale(
        hide_frame,
        from_=0,
        to=1000,
        resolution=100,
        orient="horizontal",
        length=170,
        showvalue=False,
        bg=config.BG,
        fg=config.FG,
        highlightthickness=0,
        troughcolor="#2A3B57",
        command=on_hide_slider
    )
    hide_slider.grid(row=1, column=0, sticky="ew")

    create_btn = tk.Button(
        hide_frame,
        text="Create zones",
        bg=config.BTN,
        fg=config.FG,
        width=12,
        command=create_hiding_zones
    )
    create_btn.grid(row=1, column=2, sticky="e")

    hide_frame.grid_columnconfigure(0, weight=1)

    save_btn = tk.Button(
        left,
        text="EXPORT GAME AREA (KML)",
        bg="#C62828",
        fg="white",
        font=("Segoe UI", 12, "bold"),
        height=2,
        command=save_to_kml
    )
    save_btn.grid(row=7, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 15))

    return frame