import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import pandas as pd
import numpy as np
from scipy import optimize
import matplotlib.pyplot as plt

st.set_page_config(page_title="GEE NDVI Viewer", layout="wide")

# Function to authenticate and initialize the Earth Engine
def ee_authenticate():
    try:
        ee.Initialize()
    except ee.EEException as e:
        st.error(f"Erro ao autenticar com o Google Earth Engine: {e}")
        token = st.text_input("Insira seu token de autenticação do Earth Engine:")
        if st.button("Autenticar"):
            try:
                ee.Authenticate(auth_mode='notebook', code_verifier=token)
                ee.Initialize()
                st.success("Autenticação realizada com sucesso!")
            except Exception as e:
                st.error(f"Erro ao autenticar: {e}")

# Function to add Earth Engine layer to folium map
def add_ee_layer(self, ee_image_object, vis_params, name):
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr='Map Data &copy; <a href="https://earthengine.google.com/">Google Earth Engine</a>',
        name=name,
        overlay=True,
        control=True
    ).add_to(self)

# Authenticate and initialize Earth Engine
ee_authenticate()

# Sample data processing and visualization
def main():
    if ee.data._credentials:
        # Your processing code goes here
        # Import the MODIS land cover collection
        lc = ee.ImageCollection('MODIS/006/MCD12Q1')
        # Import the MODIS land surface temperature collection
        lst = ee.ImageCollection('MODIS/006/MOD11A1')
        # Import the USGS ground elevation image
        elv = ee.Image('USGS/SRTMGL1_003')

        # Example of using the imported collections
        # Initial date of interest (inclusive)
        i_date = '2017-01-01'
        # Final date of interest (exclusive)
        f_date = '2020-01-01'

        # Selection of appropriate bands and dates for LST
        lst = lst.select('LST_Day_1km', 'QC_Day').filterDate(i_date, f_date)

        # Define the urban location of interest as a point near Lyon, France
        u_lon = 4.8148
        u_lat = 45.7758
        u_poi = ee.Geometry.Point(u_lon, u_lat)

        # Define the rural location of interest as a point away from the city
        r_lon = 5.175964
        r_lat = 45.574064
        r_poi = ee.Geometry.Point(r_lon, r_lat)

        # Get information about our region/point of interest
        scale = 1000  # scale in meters
        elv_urban_point = elv.sample(u_poi, scale).first().get('elevation').getInfo()
        lst_urban_point = lst.mean().sample(u_poi, scale).first().get('LST_Day_1km').getInfo()
        lc_urban_point = lc.first().sample(u_poi, scale).first().get('LC_Type1').getInfo()

        st.write(f"Ground elevation at urban point: {elv_urban_point} m")
        st.write(f"Average daytime LST at urban point: {round(lst_urban_point * 0.02 - 273.15, 2)} °C")
        st.write(f"Land cover value at urban point is: {lc_urban_point}")

        # Visualization with Folium
        folium.Map.add_ee_layer = add_ee_layer

        # Create a map
        lat, lon = 45.77, 4.855
        my_map = folium.Map(location=[lat, lon], zoom_start=7)

        # Add the land cover to the map object
        lc_img = lc.select('LC_Type1').filterDate(i_date).first()
        lc_vis_params = {
            'min': 1, 'max': 17,
            'palette': ['05450a', '086a10', '54a708', '78d203', '009900', 'c6b044',
                        'dcd159', 'dade48', 'fbff13', 'b6ff05', '27ff87', 'c24f44',
                        'a5a5a5', 'ff6d4c', '69fff8', 'f9ffa4', '1c0dff']
        }
        my_map.add_ee_layer(lc_img, lc_vis_params, 'Land Cover')
        my_map.add_child(folium.LayerControl())

        # Display the map
        folium_static(my_map)

if __name__ == "__main__":
    main()
