import streamlit as st
import ee
import geemap
import folium
from folium import WmsTileLayer
from streamlit_folium import folium_static
from datetime import datetime, timedelta
import json

# Streamlit Page Configuration
st.set_page_config(
    page_title="NDVI Viewer",
    page_icon="https://cdn-icons-png.flaticon.com/512/2516/2516640.png",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get help': "https://github.com/IndigoWizard/NDVI-Viewer",
        'Report a bug': "https://github.com/IndigoWizard/NDVI-Viewer/issues",
        'About': "This app was developed by [IndigoWizard](https://github.com/IndigoWizard/NDVI-Viewer) for the purpose of environmental monitoring and geospatial analysis"
    }
)

# Custom CSS for Streamlit UI
st.markdown("""
<style>
    .st-emotion-cache-1avcm0n{height: 1rem;}
    .main {scroll-behavior: smooth;}
    .st-emotion-cache-z5fcl4 {padding-block: 0;}
    .st-emotion-cache-10oheav {padding: 0 1rem;}
    .css-ge7e53 {width: fit-content;}
    .css-1kyxreq {display: block !important;}
    div.element-container:nth-child(4) > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) {
        margin: 0; padding: 0; list-style: none;
    }
    div.element-container:nth-child(4) > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) > li {
        padding: 0; margin: 0; font-weight: 600;
    }
    div.element-container:nth-child(4) > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) > li > a {
        text-decoration: none; transition: 0.2s ease-in-out; padding-inline: 10px;
    }
    div.element-container:nth-child(4) > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) > li > a:hover {
        color: rgb(46, 206, 255); transition: 0.2s ease-in-out; background: #131720; border-radius: 4px;
    }
    div.css-rklnmr:nth-child(6) > div:nth-child(1) > div:nth-child(1) > p {
        display: flex; flex-direction: row; gap: 1rem;
    }
    .st-emotion-cache-1erivf3 {display: flex; flex-direction: column; align-items: inherit; font-size: 14px;}
    .css-u8hs99.eqdbnj014 {display: flex; flex-direction: row; margin-inline: 0;}
    .st-emotion-cache-1gulkj5 {display: flex; flex-direction: column; align-items: inherit; font-size: 14px;}
    .st-emotion-cache-u8hs99 {display: flex; flex-direction: row; margin-inline: 0;}
    .ndvilegend, .reclassifiedndvi {
        transition: 0.2s ease-in-out; border-radius: 5px; box-shadow: 0 0 5px rgba(0, 0, 0, 0.2); background: rgba(0, 0, 0, 0.05);
    }
    .ndvilegend:hover, .reclassifiedndvi:hover {
        transition: 0.3s ease-in-out; box-shadow: 0 0 5px rgba(0, 0, 0, 0.8); background: rgba(0, 0, 0, 0.12); cursor: pointer;
    }
    button.st-emotion-cache-19rxjzo:nth-child(1) {width: 100%;}
</style>
""", unsafe_allow_html=True)

# Initialize Earth Engine
@st.cache_data(persist=True)
def ee_authenticate(token_name="EARTHENGINE_TOKEN"):
    geemap.ee_initialize(token_name=token_name)

def add_ee_layer(self, ee_image_object, vis_params, name):
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    layer = folium.raster_layers.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr='Map Data &copy; <a href="https://earthengine.google.com/">Google Earth Engine</a>',
        name=name,
        overlay=True,
        control=True
    )
    layer.add_to(self)

folium.Map.add_ee_layer = add_ee_layer

def satCollection(cloudRate, initialDate, updatedDate, aoi):
    collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloudRate)) \
        .filterDate(initialDate, updatedDate) \
        .filterBounds(aoi)
    
    def clipCollection(image):
        return image.clip(aoi).divide(10000)

    collection = collection.map(clipCollection)
    return collection

last_uploaded_centroid = None
def upload_files_proc(upload_files):
    global last_uploaded_centroid
    geometry_aoi_list = []

    for upload_file in upload_files:
        bytes_data = upload_file.read()
        geojson_data = json.loads(bytes_data)

        if 'features' in geojson_data and isinstance(geojson_data['features'], list):
            features = geojson_data['features']
        elif 'geometries' in geojson_data and isinstance(geojson_data['geometries'], list):
            features = [{'geometry': geo} for geo in geojson_data['geometries']]
        else:
            continue

        for feature in features:
            if 'geometry' in feature and 'coordinates' in feature['geometry']:
                coordinates = feature['geometry']['coordinates']
                geometry = ee.Geometry.Polygon(coordinates) if feature['geometry']['type'] == 'Polygon' else ee.Geometry.MultiPolygon(coordinates)
                geometry_aoi_list.append(geometry)
                last_uploaded_centroid = geometry.centroid(maxError=1).getInfo()['coordinates']

    if geometry_aoi_list:
        geometry_aoi = ee.Geometry.MultiPolygon(geometry_aoi_list)
    else:
        geometry_aoi = ee.Geometry.Point([27.98, 36.13])

    return geometry_aoi

def date_input_proc(input_date, time_range):
    end_date = input_date
    start_date = input_date - timedelta(days=time_range)
    str_start_date = start_date.strftime('%Y-%m-%d')
    str_end_date = end_date.strftime('%Y-%m-%d')
    return str_start_date, str_end_date

def main():
    ee_authenticate(token_name="EARTHENGINE_TOKEN")

    with st.sidebar:
        st.title("NDVI Viewer App")
        st.image("https://cdn-icons-png.flaticon.com/512/2516/2516640.png", width=90)
        st.subheader("Navigation:")
        st.markdown("""
            - [NDVI Map](#ndvi-viewer)
            - [Map Legend](#map-legend)
            - [Process workflow](#process-workflow-aoi-date-range-and-classification)
            - [Interpreting the Results](#interpreting-the-results)
            - [Environmental Index](#using-an-environmental-index-ndvi)
            - [Data](#data-sentinel-2-imagery-and-l2a-product)
            - [Contribution](#contribute-to-the-app)
            - [About](#about)
            - [Credit](#credit)
        """)
        st.subheader("Contact:")
        st.markdown("[![LinkedIn](https://static.licdn.com/sc/h/8s162nmbcnfkg7a0k8nq9wwqo)](https://linkedin.com/in/ahmed-islem-mokhtari) [![GitHub](https://github.githubassets.com/favicons/favicon-dark.png)](https://github.com/IndigoWizard) [![Medium](https://miro.medium.com/1*m-R_BkNf1Qjr1YbyOIJY2w.png)](https://medium.com/@Indigo.Wizard/mt-chenoua-forest-fires-analysis-with-remote-sensing-614681f468e9)")
        st.caption("ʕ •ᴥ•ʔ Star⭐the [project on GitHub](https://github.com/IndigoWizard/NDVI-Viewer/)!")

    st.title("NDVI Viewer")
    st.markdown("**Monitor Vegetation Health by Viewing & Comparing NDVI Values Through Time and Location with Sentinel-2 Satellite Images on The Fly!**")

    with st.form("input_form"):
        c1, c2 = st.columns([3, 1])
        
        with c2:
            st.info("Cloud Coverage 🌥️")
            cloud_pixel_percentage = st.slider(label="cloud pixel rate", min_value=5, max_value=100, step=5, value=85, label_visibility="collapsed")
            st.info("Upload Area Of Interest file:")
            upload_files = st.file_uploader("Create a GeoJSON file at: [geojson.io](https://geojson.io/)", accept_multiple_files=True)
            geometry_aoi = upload_files_proc(upload_files)
            st.info("Custom Color Palettes")
            accessibility = st.selectbox("Accessibility: Colorblind-friendly Palettes", ["Normal", "Deuteranopia", "Protanopia", "Tritanopia", "Achromatopsia"])

            default_ndvi_palette = ["#ffffe5", "#f7fcb9", "#78c679", "#41ab5d", "#238443", "#005a32"]
            default_reclassified_ndvi_palette = ["#a50026","#ed5e3d","#f9f7ae","#f4ff78","#9ed569","#229b51","#006837"]

            ndvi_palette = default_ndvi_palette.copy()
            reclassified_ndvi_palette = default_reclassified_ndvi_palette.copy()

            if accessibility == "Deuteranopia":
                ndvi_palette = ["#fffaa1","#f4ef8e","#9a5d67","#573f73","#372851","#191135"]
                reclassified_ndvi_palette = ["#95a600","#92ed3e","#affac5","#78ffb0","#69d6c6","#22459c","#000e69"]
            elif accessibility == "Protanopia":
                ndvi_palette = ["#a6f697","#7def75","#2dcebb","#1597ab","#0c677e","#002c47"]
                reclassified_ndvi_palette = ["#95a600","#92ed3e","#affac5","#78ffb0","#69d6c6","#22459c","#000e69"]
            elif accessibility == "Tritanopia":
                ndvi_palette = ["#cdffd7","#a1fbb6","#6cb5c6","#3a77a5","#205080","#001752"]
                reclassified_ndvi_palette = ["#ed4700","#ed8a00","#e1fabe","#99ff94","#87bede","#2e40cf","#0600bc"]
            elif accessibility == "Achromatopsia":
                ndvi_palette = ["#407de0", "#2763da", "#394388", "#272c66", "#16194f", "#010034"]
                reclassified_ndvi_palette = ["#004f3d", "#338796", "#66a4f5", "#3683ff", "#3d50ca", "#421c7f", "#290058"]

        with c1:
            col1, col2 = st.columns(2)
            today = datetime.today()
            delay = today - timedelta(days=2)

            col1.warning("Initial NDVI Date 📅")
            initial_date = col1.date_input("initial", value=delay, label_visibility="collapsed")

            col2.success("Updated NDVI Date 📅")
            updated_date = col2.date_input("updated", value=delay, label_visibility="collapsed")

            time_range = 7
            str_initial_start_date, str_initial_end_date = date_input_proc(initial_date, time_range)
            str_updated_start_date, str_updated_end_date = date_input_proc(updated_date, time_range)

    global last_uploaded_centroid

    if last_uploaded_centroid is not None:
        latitude = last_uploaded_centroid[1]
        longitude = last_uploaded_centroid[0]
        m = folium.Map(location=[latitude, longitude], tiles=None, zoom_start=12, control_scale=True)
    else:
        m = folium.Map(location=[36.45, 10.85], tiles=None, zoom_start=4, control_scale=True)

    folium.TileLayer('Open Street Map', name="Open Street Map").add_to(m)
    folium.TileLayer('cartodbdark_matter', name='Dark Basemap').add_to(m)

    initial_collection = satCollection(cloud_pixel_percentage, str_initial_start_date, str_initial_end_date, geometry_aoi)
    updated_collection = satCollection(cloud_pixel_percentage, str_updated_start_date, str_updated_end_date, geometry_aoi)

    initial_sat_imagery = initial_collection.median()
    updated_sat_imagery = updated_collection.median()

    tci_params = {
        'bands': ['B4', 'B3', 'B2'],
        'min': 0,
        'max': 1,
        'gamma': 1
    }

    def getNDVI(collection):
        return collection.normalizedDifference(['B8', 'B4'])

    initial_ndvi = getNDVI(initial_sat_imagery)
    updated_ndvi = getNDVI(updated_sat_imagery)

    ndvi_params = {
        'min': 0,
        'max': 1,
        'palette': ndvi_palette
    }

    def satImageMask(sat_image):
        masked_image = sat_image.updateMask(sat_image.gte(0))
        return masked_image

    initial_ndvi = satImageMask(initial_ndvi)
    updated_ndvi = satImageMask(updated_ndvi)

    def classify_ndvi(masked_image):
        ndvi_classified = ee.Image(masked_image) \
            .where(masked_image.gte(0).And(masked_image.lt(0.15)), 1) \
            .where(masked_image.gte(0.15).And(masked_image.lt(0.25)), 2) \
            .where(masked_image.gte(0.25).And(masked_image.lt(0.35)), 3) \
            .where(masked_image.gte(0.35).And(masked_image.lt(0.45)), 4) \
            .where(masked_image.gte(0.45).And(masked_image.lt(0.65)), 5) \
            .where(masked_image.gte(0.65).And(masked_image.lt(0.75)), 6) \
            .where(masked_image.gte(0.75), 7)

        return ndvi_classified

    initial_ndvi_classified = classify_ndvi(initial_ndvi)
    updated_ndvi_classified = classify_ndvi(updated_ndvi)

    ndvi_classified_params = {
        'min': 1,
        'max': 7,
        'palette': reclassified_ndvi_palette
    }

    if initial_date == updated_date:
        m.add_ee_layer(updated_tci_image, tci_params, 'Satellite Imagery')
        m.add_ee_layer(updated_ndvi, ndvi_params, 'Raw NDVI')
        m.add_ee_layer(updated_ndvi_classified, ndvi_classified_params, 'Reclassified NDVI')
    else:
        m.add_ee_layer(initial_tci_image, tci_params, f'Initial Satellite Imagery: {initial_date}')
        m.add_ee_layer(updated_tci_image, tci_params, f'Updated Satellite Imagery: {updated_date}')
        m.add_ee_layer(initial_ndvi, ndvi_params, f'Initial Raw NDVI: {initial_date}')
        m.add_ee_layer(updated_ndvi, ndvi_params, f'Updated Raw NDVI: {updated_date}')
        m.add_ee_layer(initial_ndvi_classified, ndvi_classified_params, f'Initial Reclassified NDVI: {initial_date}')
        m.add_ee_layer(updated_ndvi_classified, ndvi_classified_params, f'Updated Reclassified NDVI: {updated_date}')

    folium.LayerControl(collapsed=True).add_to(m)

    submitted = c2.form_submit_button("Generate map")
    if submitted:
        with c1:
            folium_static(m)
    else:
        with c1:
            folium_static(m)

    st.subheader("Map Legend:")
    col3, col4, col5 = st.columns([1, 2, 1])

    with col3:
        ndvi_legend_html = """
            <div class="ndvilegend">
                <h5>Raw NDVI</h5>
                <div style="display: flex; flex-direction: row; align-items: flex-start; gap: 1rem; width: 100%;">
                    <div style="width: 30px; height: 200px; background: linear-gradient({0},{1},{2},{3},{4},{5});"></div>
                    <div style="display: flex; flex-direction: column; justify-content: space-between; height: 200px;">
                        <span>-1</span>
                        <span style="align-self: flex-end;">1</span>
                    </div>
                </div>
            </div>
        """.format(*ndvi_palette)
        st.markdown(ndvi_legend_html, unsafe_allow_html=True)

    with col4:
        reclassified_ndvi_legend_html = """
            <div class="reclassifiedndvi">
                <h5>NDVI Classes</h5>
                <ul style="list-style-type: none; padding: 0;">
                    <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {0};">&#9632;</span> Absent Vegetation. (Water/Clouds/Built-up/Rocks/Sand Surfaces..)</li>
                    <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {1};">&#9632;</span> Bare Soil.</li>
                    <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {2};">&#9632;</span> Low Vegetation.</li>
                    <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {3};">&#9632;</span> Light Vegetation.</li>
                    <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {4};">&#9632;</span> Moderate Vegetation.</li>
                    <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {5};">&#9632;</span> Strong Vegetation.</li>
                    <li style="margin: 0.2em 0px; padding: 0;"><span style="color: {6};">&#9632;</span> Dense Vegetation.</li>
                </ul>
            </div>
        """.format(*reclassified_ndvi_palette)
        st.markdown(reclassified_ndvi_legend_html, unsafe_allow_html=True)

    st.subheader("Information")
    st.write("#### Process workflow: AOI, Date Range, and Classification")
    st.write("This app provides a simple interface to explore NDVI changes over time for a specified Area of Interest (AOI). Here's how it works:")
    st.write("1. **Upload GeoJSON AOI:** Start by uploading a GeoJSON file that outlines your Area of Interest. This defines the region where NDVI analysis will be performed. You can create any polygon-shaped area of interest at [geojson.io](https://geojson.io).")
    st.write("2. **Select Date Range:** Choose a date, this input triggers the app to gather images from a **7-days range** leading to that date. These images blend into a mosaic that highlights vegetation patterns while minimizing disruptions like clouds.")
    st.write("3. **Select Cloud Coverage Rate:** Choose a value for cloud coverage, this input triggers the app to gather images with relevant value of clouds covering the images. A higher value will gather more images but may be of poor quality, lower cloud coverage value gathers clearer images, but may have less images in the collection.")
    st.write("4. **Image Collection and Processing:** Once the date range is established, the app collects satellite images spanning that period. These images are then clipped to your chosen Area of Interest (AOI) and undergo processing to derive raw NDVI values using wavelength calculations. This method ensures that the resulting NDVI map accurately reflects the vegetation status within your specific region of interest.")
    st.write("5. **NDVI Classification:** The raw NDVI results are classified into distinct vegetation classes. This classification provides a simplified visualization of vegetation density, aiding in interpretation.")
    st.write("6. **Map Visualization:** The results are displayed on an interactive map, allowing you to explore NDVI patterns and changes within your AOI.")

    st.write("This app is designed to provide an accessible tool for both technical and non-technical users to explore and interpret vegetation health and density changes.")
    st.write("Keep in mind that while the NDVI map is a valuable tool, its interpretation requires consideration of various factors. Enjoy exploring the world of vegetation health and density!")

    st.write("#### Interpreting the Results")
    st.write("When exploring the NDVI map, keep in mind:")
    st.write("- Clouds, atmospheric conditions, and water bodies can affect the map's appearance.")
    st.write("- Satellite sensors have limitations in distinguishing surface types, leading to color variations.")
    st.write("- NDVI values vary with seasons, growth stages, and land cover changes.")
    st.write("- The map provides visual insights rather than precise representations.")

    st.write("Understanding these factors will help you interpret the results more effectively. This application aims to provide you with an informative visual aid for vegetation analysis.")

    st.write("#### Using an Environmental Index - NDVI:")
    st.write("The [Normalized Difference Vegetation Index (NDVI)](https://eos.com/make-an-analysis/ndvi/) is an essential environmental index that provides insights into the health and density of vegetation. It is widely used in remote sensing and geospatial analysis to monitor changes in land cover, vegetation growth, and environmental conditions.")
    st.write("NDVI is calculated using satellite imagery that captures both Near-Infrared **(NIR)** and Red **(R)** wavelengths. The formula is:")
    st.latex(r'\text{NDVI} = \frac{\text{NIR} - \text{R}}{\text{NIR} + \text{R}}')
    st.write("NDVI values range from **[-1** to **1]**, with higher values indicating denser and healthier vegetation. Lower values represent non-vegetated surfaces like water bodies, bare soil, or built-up areas.")

    st.write("#### Data: Sentinel-2 Imagery and L2A Product")
    st.write("This app utilizes **Sentinel-2 Level-2A atmospherically corrected Surface Reflectance images**. The [Sentinel-2 satellite constellation](https://sentinels.copernicus.eu/web/sentinel/user-guides/sentinel-2-msi/applications) consists of twin satellites (Sentinel-2A and Sentinel-2B) that capture high-resolution multispectral imagery of the Earth's surface.")
    st.write("The [Level-2A](https://sentinels.copernicus.eu/web/sentinel/user-guides/sentinel-2-msi/product-types/level-2a) products have undergone atmospheric correction, enhancing the accuracy of surface reflectance values. These images are suitable for various land cover and vegetation analyses, including NDVI calculations.")

    st.header("Contribute to the App")
    con1, con2 = st.columns(2)
    con1.image("https://www.pixenli.com/image/SoL3iZMG")
    con2.markdown("""
        Contributions are welcome from the community to help improve this app! Whether you're interested in fixing bugs 🐞, implementing a new feature 🌟, or enhancing the user experience 🪄, your contributions are valuable.
        The project is listed under **Hacktoberfest** label for those of you [Hacktoberfest](https://hacktoberfest.com/) enthusiasts! Since the reward for contributing 4 PRs is getting a tree planted in your name through [TreeNation](https://tree-nation.com/), I see it fits the theme of this project.
    """)
    st.markdown("""
        #### Ways to Contribute
        - **Report Issues**: If you come across any bugs, issues, or unexpected behavior, please report them in the [GitHub Issue Tracker](https://github.com/IndigoWizard/NDVI-Viewer/issues).
        - **Suggest Enhancements**: Have an idea to make the app better? Share your suggestions in the [GitHub Issue Tracker](https://github.com/IndigoWizard/NDVI-Viewer/issues).
        - **Code Contributions**: If you're comfortable with coding, you can contribute by submitting pull requests against the `dev` branch of the [Project's GitHub repository](https://github.com/IndigoWizard/NDVI-Viewer/).
    """)

    st.subheader("About:")
    st.markdown("This project was first developed by me ([IndigoWizard](https://github.com/IndigoWizard)) and [Emmarie-Ahtunan](https://github.com/Emmarie-Ahtunan) as a submission to the **Environmental Data Challenge** of [Global Hack Week: Data](https://ghw.mlh.io/) by [Major League Hacking](https://mlh.io/). I continued developing the base project to make it a feature-complete app. Check the project's GitHub Repo here: [IndigoWizard/NDVI-Viewer](https://github.com/IndigoWizard/NDVI-Viewer)",  unsafe_allow_html=True)
    st.image("https://www.pixenli.com/image/Hn1xkB-6")

    st.subheader("Credit:")
    st.markdown("""The app was developed by [IndigoWizard](https://github.com/IndigoWizard) using; [Streamlit](https://streamlit.io/), [Google Earth Engine](https://github.com/google/earthengine-api) Python API, [geemap](https://github.com/gee-community/geemap), [Folium](https://github.com/python-visualization/folium). Agriculture icons created by <a href="https://www.flaticon.com/free-icons/agriculture" title="agriculture icons">dreamicons - Flaticon</a>""", unsafe_allow_html=True)
    
    st.markdown("""
    <style>
        iframe {width: 100%;}
        .css-1o9kxky.e1f1d6gn0 {border: 2px solid #ffffff4d; border-radius: 4px; padding: 1rem;}
    </style>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
