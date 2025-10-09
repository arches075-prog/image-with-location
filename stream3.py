import streamlit as st
import gpxpy
import os
import json
from PIL import Image
import tempfile
from io import BytesIO
import xml.etree.ElementTree as ET

st.set_page_config(page_title="GeoJSON Utility", layout="wide")

# ----------------------------
# Helper: Parse GPX
# ----------------------------
def parse_gpx(file):
    gpx = gpxpy.parse(file)
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points.append({
                    "name": point.name if point.name else "",
                    "lat": point.latitude,
                    "lon": point.longitude
                })
    for wp in gpx.waypoints:
        points.append({
            "name": wp.name if wp.name else "",
            "lat": wp.latitude,
            "lon": wp.longitude
        })
    return points

# ----------------------------
# Helper: Parse KML (all coords, robust)
# ----------------------------
def parse_kml(file):
    content = file.read()
    if isinstance(content, bytes):
        content = content.decode('utf-8')
    # Remove XML declaration
    if content.startswith("<?xml"):
        content = content.split("?>", 1)[1]

    root = ET.fromstring(content)
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}

    features = []

    for placemark in root.findall('.//kml:Placemark', ns):
        name_elem = placemark.find('kml:name', ns)
        name = name_elem.text if name_elem is not None else ""

        # --- Point ---
        pt = placemark.find('.//kml:Point/kml:coordinates', ns)
        if pt is not None:
            lon, lat, *_ = map(float, pt.text.strip().split(','))
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"name": name}
            })

        # --- LineString ---
        for line in placemark.findall('.//kml:LineString/kml:coordinates', ns):
            coords = []
            for c in line.text.strip().split():
                lon, lat, *_ = map(float, c.split(','))
                coords.append([lon, lat])
            if coords:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {"name": name}
                })

        # --- Polygon (outerBoundary) ---
        for poly in placemark.findall('.//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates', ns):
            coords = []
            for c in poly.text.strip().split():
                lon, lat, *_ = map(float, c.split(','))
                coords.append([lon, lat])
            if coords:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "properties": {"name": name}
                })

    return features

# ----------------------------
# Module Tabs
# ----------------------------
tab1, tab2 = st.tabs([
    "📍 Image/Video + GPX/KML → Individual GeoJSONs",
    "🗺️ KML/GPX → GeoJSON Converter"
])

# ======================================================
# MODULE 1
# ======================================================
with tab1:
    st.title("📸 Image/Video + GPX/KML to Individual GeoJSON for Arches")

    file_type = st.selectbox("Select Geolocation File Type", ["GPX", "KML"])

    uploaded_files = st.file_uploader(
        "Upload Images/Videos", accept_multiple_files=True,
        type=["jpg", "jpeg", "png", "mp4", "mov", "avi"]
    )
    geo_file = st.file_uploader(f"Upload {file_type} File", type=[file_type.lower()])

    if uploaded_files and geo_file:
        st.success(f"{file_type} and media files uploaded successfully!")

        # Parse geolocation file
        geo_points = parse_gpx(geo_file) if file_type == "GPX" else parse_kml(geo_file)

        if not geo_points:
            st.warning(f"No points found in {file_type} file!")
        else:
            # Build lookup for media matching (only for points)
            geo_dict = {os.path.basename(p["properties"]["name"] if "properties" in p else p["name"]): p
                        for p in geo_points if (("properties" in p and "name" in p["properties"]) or "name" in p)}

            with tempfile.TemporaryDirectory() as tmpdir:
                for idx, file in enumerate(uploaded_files):
                    file_path = os.path.join(tmpdir, file.name)
                    with open(file_path, "wb") as f:
                        f.write(file.read())

                    match = geo_dict.get(file.name)
                    if match:
                        st.markdown(f"### 📍 {file.name}")

                        geom = match["geometry"]
                        coords = geom.get("coordinates") if geom else (None, None)
                        lat, lon = coords[1], coords[0] if coords else (None, None)
                        if lat is not None and lon is not None:
                            st.write(f"Location: {lat}, {lon}")

                        # Show image/video
                        if file.type.startswith("image"):
                            img = Image.open(file_path)
                            st.image(img, caption=f"{file.name} @ ({lat}, {lon})", use_container_width=True)
                        elif file.type.startswith("video"):
                            st.video(file_path)

                        st.json(match)

                        default_name = os.path.splitext(file.name)[0] + ".geojson"
                        custom_name = st.text_input(
                            f"Enter GeoJSON filename for {file.name}:",
                            value=default_name,
                            key=f"name_input_{idx}"
                        )

                        # Download GeoJSON
                        st.download_button(
                            label=f"⬇️ Download GeoJSON for {file.name}",
                            data=json.dumps(match, indent=2),
                            file_name=custom_name,
                            mime="application/geo+json",
                            key=f"geojson_dl_{idx}"
                        )

                        with open(file_path, "rb") as f:
                            st.download_button(
                                label=f"⬇️ Download {file.name}",
                                data=f,
                                file_name=file.name,
                                mime=file.type,
                                key=f"file_dl_{idx}"
                            )
                        st.markdown("---")
                    else:
                        st.error(f"❌ {file.name} not found in {file_type} file.")

# ======================================================
# MODULE 2
# ======================================================
with tab2:
    st.title("🗺️ Convert KML/GPX to GeoJSON")

    convert_file = st.file_uploader("Upload KML or GPX file", type=["kml", "gpx"])

    if convert_file:
        ext = os.path.splitext(convert_file.name)[1].lower()
        st.success(f"Uploaded {convert_file.name}")

        if ext == ".gpx":
            geo_points_raw = parse_gpx(convert_file)
            geo_points = []
            for p in geo_points_raw:
                geo_points.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
                    "properties": {"name": p["name"]}
                })
        elif ext == ".kml":
            geo_points = parse_kml(convert_file)
        else:
            geo_points = []

        if not geo_points:
            st.warning("No valid points found in the file.")
        else:
            geojson = {
                "type": "FeatureCollection",
                "features": geo_points
            }

            st.subheader("✅ GeoJSON Preview")
            st.json(geojson)

            out_name = os.path.splitext(convert_file.name)[0] + ".geojson"
            st.download_button(
                label="⬇️ Download GeoJSON File",
                data=json.dumps(geojson, indent=2),
                file_name=out_name,
                mime="application/geo+json"
            )
