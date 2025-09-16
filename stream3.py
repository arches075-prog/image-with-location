import streamlit as st
import gpxpy
import os
import json
from PIL import Image
import tempfile

# --- Helper: Parse GPX file ---
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


# --- Streamlit UI ---
st.title("Image/Video + GPX to Individual GeoJSON for Arches")

uploaded_files = st.file_uploader("Upload Images/Videos", accept_multiple_files=True,
                                  type=["jpg", "jpeg", "png", "mp4", "mov", "avi"])
gpx_file = st.file_uploader("Upload GPX File", type=["gpx"])

if uploaded_files and gpx_file:
    st.success("Files uploaded successfully!")

    # Parse GPX
    gpx_points = parse_gpx(gpx_file)

    if not gpx_points:
        st.warning("No points found in GPX file!")
    else:
        # Make dictionary {filename: (lat,lon)}
        gpx_dict = {os.path.basename(p["name"]): (p["lat"], p["lon"]) for p in gpx_points if p["name"]}

        # Temporary directory for storing uploaded files
        with tempfile.TemporaryDirectory() as tmpdir:
            for idx, file in enumerate(uploaded_files):
                file_path = os.path.join(tmpdir, file.name)
                with open(file_path, "wb") as f:
                    f.write(file.read())

                if file.name in gpx_dict:
                    lat, lon = gpx_dict[file.name]
                    st.markdown(f"### 📍 {file.name}")
                    st.write(f"Location: {lat}, {lon}")

                    # Show image/video
                    if file.type.startswith("image"):
                        img = Image.open(file_path)
                        st.image(img, caption=f"{file.name} @ ({lat}, {lon})", use_container_width=True)
                    elif file.type.startswith("video"):
                        st.video(file_path)

                    # Build GeoJSON for this file
                    geojson = {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Point",
                                    "coordinates": [lon, lat]
                                },
                                "properties": {
                                    "filename": file.name,
                                    "filetype": file.type
                                }
                            }
                        ]
                    }

                    # Show GeoJSON snippet in app
                    st.json(geojson)

                    # Text input for custom filename
                    default_name = os.path.splitext(file.name)[0] + ".geojson"
                    custom_name = st.text_input(
                        f"Enter GeoJSON filename for {file.name}:",
                        value=default_name,
                        key=f"name_input_{idx}"
                    )

                    # Download buttons
                    st.download_button(
                        label=f"⬇️ Download GeoJSON for {file.name}",
                        data=json.dumps(geojson, indent=2),
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
                    st.write(f"❌ {file.name} not found in GPX file.")
