import threading
import queue
import random

import pandas as pd
import overpy

import config


def _run_with_timeout(func, timeout=8):
    q = queue.Queue()

    def wrapper():
        try:
            q.put(func())
        except Exception as e:
            q.put(e)

    t = threading.Thread(target=wrapper, daemon=True)
    t.start()

    try:
        result = q.get(timeout=timeout)
    except queue.Empty:
        raise TimeoutError("Overpass request timed out")

    if isinstance(result, Exception):
        raise result

    return result


def _save_bounding_box(point1_entry, point2_entry):
    """
    Read bounding box from two Entry widgets and store in config.bound_box.
    """
    try:
        lat1, lon1 = map(float, point1_entry.get().split(","))
        lat2, lon2 = map(float, point2_entry.get().split(","))

        config.bound_box = [
            min(lat1, lat2),  # south
            min(lon1, lon2),  # west
            max(lat1, lat2),  # north
            max(lon1, lon2),  # east
        ]
        return True
    except Exception:
        return False


def fetch_osm_data(osm_filter, type_name, status_label, point1_entry, point2_entry):
    """
    Fetch OSM node data using Overpass and store results in config.all_data.

    Returns:
        pandas.DataFrame on success, or None on failure/empty.
    """
    if not _save_bounding_box(point1_entry, point2_entry):
        status_label.config(text="Invalid bounding box. Use: lat, lon")
        return None

    south, west, north, east = config.bound_box

    query = f"""
    node[{osm_filter}]({south},{west},{north},{east});
    out;
    """

    mirrors = config.overpass_mirrors[:]
    random.shuffle(mirrors)

    for url in mirrors:
        host = url.split("/")[2] if "://" in url else url  # shorter status text
        try:
            status_label.config(text=f"Trying {host}...")
            status_label.update_idletasks()

            api = overpy.Overpass(url=url)
            result = _run_with_timeout(lambda: api.query(query), timeout=8)

            rows = [{
                "Name": node.tags.get("name", "Unnamed"),
                "Type": type_name,
                "Latitude": float(node.lat),
                "Longitude": float(node.lon),
            } for node in result.nodes]

            if not rows:
                status_label.config(text=f"No {type_name} found.")
                return None

            df = pd.DataFrame(rows)

            config.all_data[type_name] = df
            config.dedup_valid = False

            status_label.config(text=f"Fetched {len(df)} {type_name} points.")
            return df

        except TimeoutError:
            status_label.config(text=f"Timeout on {host}")
            status_label.update_idletasks()

        except Exception:
            status_label.config(text=f"Error on {host}")
            status_label.update_idletasks()

    status_label.config(text=f"Failed to fetch {type_name} (all servers).")
    return None