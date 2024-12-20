from flask import Blueprint, render_template, request, jsonify
import requests
from shapely.geometry import shape
import json
import geopandas as gpd
import io
import os

blueprint = Blueprint('intersect',__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
map_path = os.path.join(BASE_DIR, '..', 'static', 'lup_intersect.html')

# URL for your WFS layers (replace with actual WFS URLs)
WFS_LAYER_1_URL = 'https://openmaps.gov.bc.ca/geo/pub/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=pub%3AWHSE_LAND_USE_PLANNING.RMP_PLAN_LEGAL_POLY_SVW&outputFormat=json&srsName=EPSG%3A4326&sortBy=OBJECTID&limit=10000&offset=0&bbox=743161%2C1112127%2C898012%2C1291756%2Curn%3Aogc%3Adef%3Acrs%3AEPSG%3A3005'
WFS_LAYER_2_URL = 'https://openmaps.gov.bc.ca/geo/pub/ows?service=WFS&version=2.0.0&request=GetFeature&typeName=pub%3AWHSE_LAND_USE_PLANNING.RMP_PLAN_NON_LEGAL_POLY_SVW&outputFormat=json&srsName=EPSG%3A4326&sortBy=OBJECTID&limit=10000&offset=0&bbox=743161%2C1112127%2C898012%2C1291756%2Curn%3Aogc%3Adef%3Acrs%3AEPSG%3A3005'

def get_wfs_data(url):
    """
    Function to query a WFS layer and return the response as GeoJSON.
    """
    response = requests.get(url)
    return response.json()

def intersect_with_wfs(uploaded_gdf, wfs_url):
    # Fetch WFS data as GeoJSON from the WFS URL
    response = requests.get(wfs_url)
    
    if response.status_code != 200:
        raise Exception(f"Failed to fetch WFS data: {response.status_code}")
    
    # Get the content of the response (bytes)
    wfs_data = response.content
    
    # Read the WFS data into a GeoDataFrame using BytesIO
    with io.BytesIO(wfs_data) as byte_stream:
        wfs_gdf = gpd.read_file(byte_stream)

    # Ensure both GeoDataFrames have the same CRS
    if uploaded_gdf.crs != wfs_gdf.crs:
        wfs_gdf = wfs_gdf.to_crs(uploaded_gdf.crs)

    # Perform intersection
    # intersected_data = gpd.overlay(uploaded_gdf, wfs_gdf, how='intersection')
    intersected_data = gpd.sjoin(wfs_gdf, uploaded_gdf, how='inner', predicate='intersects')

    # Convert Timestamp columns to string before serializing to JSON
    for column in intersected_data.select_dtypes(include=['datetime']).columns:
        intersected_data[column] = intersected_data[column].astype(str)

    # Return the GeoDataFrame (not the JSON string)
    return intersected_data

@blueprint.route('/intersect', methods=['GET', 'POST'])
def intersect():
    with open(map_path, 'r') as f:
        leaflet_map = f.read()
    if request.method == 'POST':
        # Step 1: Read the uploaded file
        uploaded_file = request.files['file']
        uploaded_gdf = None

        if uploaded_file.filename.endswith('.geojson'):
            uploaded_gdf = gpd.read_file(uploaded_file)
        elif uploaded_file.filename.endswith('.shp'):
            uploaded_gdf = gpd.read_file(uploaded_file)
        elif uploaded_file.filename.endswith('.kml'):
            uploaded_gdf = gpd.read_file(uploaded_file)

        if uploaded_gdf is not None:
            intersected_data_1 = intersect_with_wfs(uploaded_gdf, WFS_LAYER_1_URL)
            intersected_data_2 = intersect_with_wfs(uploaded_gdf, WFS_LAYER_2_URL)

            # Convert DataFrames to list of dictionaries for easy table rendering
            intersected_data_1_list = intersected_data_1[['STRGC_LAND_RSRCE_PLAN_NAME', 'LEGAL_FEAT_OBJECTIVE', 
                                                        'LEGALIZATION_DATE', 'ENABLING_DOCUMENT_TITLE', 
                                                        'ENABLING_DOCUMENT_URL', 'RSRCE_PLAN_METADATA_LINK']].to_dict(orient='records')
            
            intersected_data_2_list = intersected_data_2[['NON_LEGAL_FEAT_ID', 'STRGC_LAND_RSRCE_PLAN_NAME',
                                                        'NON_LEGAL_FEAT_OBJECTIVE', 'ORIGINAL_DECISION_DATE']].to_dict(orient='records')

            return render_template(
                'intersect.html',
                intersected_data_1=intersected_data_1_list,
                intersected_data_2=intersected_data_2_list,
                leaflet_map=leaflet_map
            )
    # For GET requests, set default values for the data variables
    return render_template(
        'intersect.html',
        leaflet_map=leaflet_map,
        intersected_data_1=None,
        intersected_data_2=None
    )