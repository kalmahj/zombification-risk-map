# -*- coding: utf-8 -*-
"""
Created on Fri Nov 14 22:47:37 2025

@author: Kalma Hazara
"""

###############################################################################
# Zombification Map, France #
###############################################################################

###############################################################################
# This code is a tutorial on how to make a zombification map with a score per IRIS. 
# Datasets that will be used :
    # Cemetry points (Open Street Map)
    # Population Density (INSEE)
    # 70+ year old ratio (INSEE)
###############################################################################

###############################################################################
# The higher the score :
    # The closer the IRIS is from a cemetery
    # The higher the population density
    # The higher the 70+ year old ratio
###############################################################################

###############################################################################
# IMPORT LIBRARIES #
###############################################################################
import pandas as pd
import geopandas as gpd
from sklearn.preprocessing import MinMaxScaler
import folium as fol
import branca.colormap as cm
import numpy as np
import warnings
# import osmnx as ox

###############################################################################

###############################################################################
#%% STEP 0 : Let the user choose the city/region/department #
###############################################################################

city = input("Warning! A zombie apocalypse is on the rise! \n\nPut your INSEE code to know your city's' risk! \nBe safe!\n\n Enter here :")

warnings.filterwarnings(action='ignore')
print("\nGenerating zombie risk index. Please wait...")

###############################################################################
#%% STEP 1.1 : Create Population Density Geodataframe per IRIS #
###############################################################################

# File import
contour_iris = gpd.read_file (r"data\CONTOURS-IRIS_2-1__SHP__FRA_2022-01-01\CONTOURS-IRIS_2-1__SHP__FRA_2022-01-01\CONTOURS-IRIS\1_DONNEES_LIVRAISON_2022-06-00180\CONTOURS-IRIS_2-1_SHP_LAMB93_FXX-2022\CONTOURS-IRIS.shp")
population_insee = pd.read_csv (r"data\base-ic-evol-struct-pop-2022.CSV", sep = ";")

# Calculate the surface area of each iris
contour_iris = contour_iris.to_crs({'init': 'epsg:2154'}) # Change the CRS so the unit is in meters
contour_iris["area"] = contour_iris['geometry'].area/ 10**6 # area in km²

# Merge files population data on iris outline file
population_insee["IRIS"] = population_insee["IRIS"].astype(str) # transform in string
population_insee['IRIS'] = population_insee['IRIS'].str.zfill(9) # put a 0 at the beginning if there are only 8 digits
population_insee.rename(columns = {'IRIS' : 'CODE_IRIS'}, inplace = True) # rename for the merge

contour_iris['CODE_IRIS'] = contour_iris['CODE_IRIS'].astype(str) # transform in string

population_iris = contour_iris.merge(population_insee[['CODE_IRIS', 'P22_POP']], on='CODE_IRIS', how='left') # merge the population column on the iris outline file

# Calculate the population density per km²
population_iris['Density km²'] = population_iris['P22_POP'] / population_iris['area']

###############################################################################
#%% STEP 1.2 : Create Old people ratio Geodataframe per IRIS #
###############################################################################

# Merge number of 75+ year olds on our gdf
population_iris = population_iris.merge(population_insee[['CODE_IRIS', 'P22_POP75P']], on='CODE_IRIS', how='left')

# Percentage of 75+ year olds
population_iris["% 75+ ans"] = (population_iris['P22_POP75P'] * 100) / population_iris['P22_POP']

# =============================================================================
# #%% STEP 1.3 : Create disabled people ratio
# =============================================================================
#Import csv file of disabled people : https://www.insee.fr/fr/statistiques/6679585
disabled = pd.read_csv(r"data\data_CAF2021_IRIS.csv", sep=';')

#Fill NAs with the average of the whole column
#AAAH : people who are recieving AAH (financial privilege for diabled people)
disabled['AAAH'] =  disabled['AAAH'].fillna(disabled['AAAH'].mean())

#Merge disbled people data
disabled['CODGEO'] = disabled['CODGEO'].astype(str)
population_iris = pd.merge(population_iris, disabled[['CODGEO', 'AAAH']], how='left',
                           left_on='CODE_IRIS', right_on='CODGEO')

#Replace the remaining nan values with 2
population_iris['AAAH'] =  population_iris['AAAH'].fillna(2)

#Remove codgeo column
population_iris = population_iris.drop('CODGEO', axis=1)

###############################################################################
#%% STEP 1.4 : Retrieve cemetries from BDTOPO #
###############################################################################
#Import cemetries data from BDTOPO 2026
cemetries = gpd.read_file(r"data\cimetieres.gpkg")

#Dissolve oevrlapping cemetries
cemetries = cemetries.dissolve().explode()

#Compute distance with the closest cemetry
population_iris = gpd.sjoin_nearest(population_iris, cemetries[['cleabs', 'geometry']], how='left', 
                             distance_col='distance_cemetry', rsuffix='_cemetry')

#Drop duplicates (IRISs with 2 cemetries at the same distance)
population_iris = population_iris.drop_duplicates(subset=['CODE_IRIS'], keep='first')

###############################################################################
#%% STEP 1.5 : Retrieve airfields/airports from BDTOPO #
###############################################################################
#Import cemetries data from BDTOPO 2026
airfields = gpd.read_file(r"data\BDTopoExport_20260306_1443\bd_topo_extract.gpkg")

population_iris = population_iris.to_crs(2154)
airfields = airfields.to_crs(2154)

# Dissolve overlapping airfields
airfields = airfields.dissolve().explode()

# Compute distance with the closest airfield
population_iris = gpd.sjoin_nearest(population_iris, airfields[['cleabs', 'geometry']], how='left', 
                             distance_col='distance_airfield', rsuffix='_airport')

# Drop duplicates (IRISs with 2 airfields at the same distance)
population_iris = population_iris.drop_duplicates(subset=['CODE_IRIS'], keep='first')

###############################################################################
#%% STEP 1.6 : Retrieve weapons shops from OSM #
###############################################################################
weapon_shops = gpd.read_file(r"data\weapon_shops.geojson", driver = 'GeoJSON')
weapon_shops = weapon_shops.to_crs(2154)
#Compute distance with the closest airfield
population_iris = gpd.sjoin_nearest(population_iris, weapon_shops[['full_id', 'geometry']], how='left', 
                             distance_col='distance_weapon_shops', rsuffix='_weapons')

#Drop duplicates (IRISs with 2 weapon shops at the same distance)
population_iris = population_iris.drop_duplicates(subset=['CODE_IRIS'], keep='first')

# If you would like to use an OSM query to retrieve the weapon points... But it's very slow :P
"""
tags = {"shop" : "weapons"}
place = "France"
weapon_shops = ox.features.features_from_place(place, tags)
"""

###############################################################################
#%% STEP 1.7 : number of cemetries by iris #
###############################################################################
# Spatial join the cemetries to the main df
joinjoin = population_iris.sjoin(cemetries, how='left')

# Count how many cemetries are inside or intersect each IRIS
nbr = joinjoin.groupby('CODE_IRIS').size().to_frame(name='nb_cemetries')

# Merge the count back to the main df
population_iris = pd.merge(population_iris, nbr, left_on='CODE_IRIS',
                           right_index=True, how='left') 

# Fill NaN values with 0 for IRIS regions that have no cemeteries
population_iris['nb_cemetries'] = population_iris['nb_cemetries'].fillna(0)

###############################################################################
#%% STEP 2 : Data normalisation for zombification index #
###############################################################################
scaler = MinMaxScaler()
def normalize_column(series):
    # Transform in float, reshape for sklearn, fit_transform, and return as a flat series
    series = series.astype(float)
    return scaler.fit_transform(series.values.reshape(-1, 1)).ravel()

# Normalize all values
norm_cemetery = normalize_column(population_iris['distance_cemetry'])
norm_density = normalize_column(population_iris['Density km²'])
norm_elderly = normalize_column(population_iris['% 75+ ans'])
norm_disabled = normalize_column(population_iris['AAAH'])
norm_airfield = normalize_column(population_iris['distance_airfield'])
norm_weapons = normalize_column(population_iris['distance_weapon_shops'])
norm_nb_cemetry = normalize_column(population_iris['nb_cemetries'])

# Computing zombification score
population_iris['zombie_score'] = (
    (1 - norm_cemetery) * 0.15 + 
    norm_nb_cemetry * 0.20 +
    norm_density * 0.15 + 
    norm_elderly * 0.10 + 
    norm_disabled * 0.10 + 
    (1 - norm_airfield) * 0.20 + 
    (1 - norm_weapons) * 0.10
)

population_iris.to_file(r"zombie_grrr.gpkg")

###############################################################################
#%% STEP 2.1 : Delete columns to lighten and optimise the code execution #
###############################################################################

population_iris_filtered = population_iris.drop(['IRIS', 'NOM_IRIS', 'TYP_IRIS', 'area', 'P22_POP', 'Density km²', 'P22_POP75P', '% 75+ ans',
       'AAAH', 'index__cemetry', 'cleabs_left', 'distance_cemetry',
       'index__airport', 'cleabs__airport', 'distance_airfield',
       'index__weapons', 'full_id', 'distance_weapon_shops', 'nb_cemetries'], axis=1, errors='ignore')

###############################################################################
#%% STEP 3 : Interactive folium map of zombification #
###############################################################################

# Filter one commune
test_com = population_iris_filtered[population_iris_filtered['INSEE_COM'] == city]

# Make sure that the CRS is in WGS 84 in order to fit Folium
test_com = test_com.to_crs({'init': 'epsg:4326'})

# Generate automatic bounds in order to zoom onto desired location
list_bounds = test_com.total_bounds.tolist()
list_bounds = [[list_bounds[1], list_bounds[0]], [list_bounds[3], list_bounds[2]]]

# I choose the map layer I would like
zombie_map = fol.Map(tiles='OpenStreetMap')
fol.GeoJson(test_com).add_to(zombie_map)

# Activate the bounds 
zombie_map.fit_bounds(list_bounds)

# Add popups
style_function = lambda x: {'fillColor': '#ffffff', 
                            'color':'#000000', 
                            'fillOpacity': 0.1, 
                            'weight': 0.1}
highlight_function = lambda x: {'fillColor': '#000000', 
                                'color':'#000000', 
                                'fillOpacity': 0.50, 
                                'weight': 0.1}
NIL = fol.features.GeoJson(
    data = test_com,
    style_function=style_function, 
    control=False,
    highlight_function=highlight_function,  
    tooltip=fol.features.GeoJsonTooltip(
        fields=['NOM_COM','zombie_score'],
        aliases=['Commune','Zombie Risk Index'],
        style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;") 
    )
)
zombie_map.add_child(NIL)
zombie_map.keep_in_front(NIL)

# Create chloropleth map
# Dynamically calculate 6 clean bins between the minimum and maximum zombie scores for this city
min_score = test_com["zombie_score"].min()
max_score = test_com["zombie_score"].max()

# Create 7 edge values to form 6 distinct bins, rounded neatly
# We add a tiny buffer (-0.01 and +0.01) so precise edge values are safely contained
dynamic_bins = list(np.linspace(min_score - 0.01, max_score + 0.01, 7))

# 2. Create choropleth map using the dynamic bins
fol.Choropleth(
    geo_data = test_com[["CODE_IRIS", "geometry"]],
    name="Zombie Score",
    data = test_com,  # <-- FIXED: Changed from population_iris_filtered to test_com
    columns= ["CODE_IRIS", "zombie_score"], 
    key_on="feature.properties.CODE_IRIS",
    fill_color= "RdYlBu_r",
    fill_opacity=0.7,
    line_opacity=0.1,
    legend_name="Zombie risk index (%)",
    highlight = True,
    bins = dynamic_bins  
).add_to(zombie_map)

# Save result
outpath = input (r"Calculation done ! Insert here the directory path where you want to save your map (leave empty for current directory): ")
outpath = outpath.strip() if outpath.strip() else '.'
zombie_map.save(outpath + r'\zombie_map.html')

print(f"\n\nGo to your files! The map has been generated at : \n{outpath}")





