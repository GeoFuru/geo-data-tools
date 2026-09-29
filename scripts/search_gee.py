import ee
import geopandas as gpd

from pathlib import Path
from shapely.geometry import Polygon, MultiPolygon



# GENERAL CONFIGURATION
GEOGRAPHIC_CRS = "EPSG:4326"
EXPORT_CRS = "EPSG:32719"

DEFAULT_MARGIN_KM = 10

DEFAULT_DRIVE_FOLDER = "GEE_Busqueda"



# DATASET CATALOG
DATASETS = {

    1: {
        "name": "Sentinel-2 RGB",
        "description": "Sentinel-2 RGB scene with lowest cloud cover",
        "type": "sentinel2",
        "dependencies": [],
    },

    2: {
        "name": "NDVI",
        "description": "Sentinel-2 vegetation index",
        "type": "sentinel2_ndvi",
        "dependencies": [],
    },

    3: {
        "name": "NDBI",
        "description": "Sentinel-2 built-up area index",
        "type": "sentinel2_ndbi",
        "dependencies": [],
    },

    4: {
        "name": "NDWI",
        "description": "Sentinel-2 water index",
        "type": "sentinel2_ndwi",
        "dependencies": [],
    },

    5: {
        "name": "DEM Copernicus GLO-30",
        "description": "Digital elevation model",
        "type": "dem",
        "dependencies": [],
    },

    6: {
        "name": "ESA WorldCover",
        "description": "Land cover and land use",
        "type": "worldcover",
        "dependencies": [],
    },

    7: {
        "name": "Sentinel-1 VV",
        "description": "Sentinel-1 SAR radar, VV polarization",
        "type": "sentinel1_vv",
        "dependencies": [],
    },

    8: {
        "name": "Sentinel-1 VH",
        "description": "Sentinel-1 SAR radar, VH polarization",
        "type": "sentinel1_vh",
        "dependencies": [],
    },

    9: {
        "name": "Dynamic World",
        "description": "Sentinel-2 land cover and land use at 10 m",
        "type": "dynamic_world",
        "dependencies": [],
    },

    10: {
        "name": "JRC Global Surface Water",
        "description": "Historical surface water distribution",
        "type": "jrc_water",
        "dependencies": [],
    },

    11: {
        "name": "MODIS Land Surface Temperature",
        "description": "Land surface temperature",
        "type": "lst",
        "dependencies": [],
    },

    12: {
        "name": "CHIRPS Precipitation",
        "description": "Daily precipitation",
        "type": "chirps",
        "dependencies": [],
    },

    13: {
        "name": "MODIS Evapotranspiration",
        "description": "Land evapotranspiration",
        "type": "et",
        "dependencies": [],
    },

    14: {
        "name": "Global Forest Canopy Height",
        "description": "Global forest canopy height",
        "type": "canopy_height",
        "dependencies": [],
    },

}



# AUTHENTICATION / INITIALIZATION
def initialize_earth_engine(project_id):

    print("\n" + "=" * 70)
    print("EARTH ENGINE")
    print("=" * 70)

    try:

        ee.Initialize(
            project=project_id
        )

        print(
            "✓ Earth Engine initialized successfully."
        )

    except Exception as e:

        message = str(e).lower()

        if (
            "authentication" in message
            or "credentials" in message
            or "not authenticated" in message
            or "no credentials" in message
        ):

            print(
                "\nNo active Earth Engine session was found. "
                "de Earth Engine."
            )

            print(
                "Authentication will start.\n"
            )

            ee.Authenticate()

            ee.Initialize(
                project=project_id
            )

            print(
                "✓ Earth Engine authenticated "
                "and initialized successfully."
            )

        else:

            raise



# DATA INPUT
def get_text(message, default_value=None):

    if default_value is not None:

        response = input(
            f"{message} [{default_value}]: "
        ).strip()

        if not response:
            return default_value

        return response

    return input(
        f"{message}: "
    ).strip()


def get_float(message, default_value=None):

    while True:

        response = get_text(
            message,
            default_value
        )

        try:

            return float(response)

        except ValueError:

            print(
                "⚠ Enter a valid number."
            )



# GEE PROJECT
def get_project():

    print("You can enter:")
    print("  projects/my-project")
    print("or simply:")
    print("  my-project")
    print("or paste the Google Cloud / Earth Engine URL")
    print()

    input_value = input(
        "Google Earth Engine project: "
    ).strip()

    if "?project=" in input_value:

        input_value = input_value.split(
            "?project=",
            1
        )[1]

        input_value = input_value.split(
            "&",
            1
        )[0]

    if input_value.startswith("projects/"):

        input_value = input_value[
            len("projects/"):
        ]

    project_id = input_value.strip()

    if not project_id:

        raise ValueError(
            "Could not identify the Project ID."
        )

    return project_id


def build_project_link(project_id):

    return (
        "https://code.earthengine.google.com/"
        f"?project={project_id}"
    )



# STUDY AREA
def load_area(path):

    print("\n📂 Loading AOI...")

    gdf = gpd.read_file(path)

    if gdf.empty:
        raise ValueError(
            "The AOI file is empty."
        )

    if gdf.crs is None:
        raise ValueError(
            "The AOI has no defined coordinate reference system."
        )

    print(f"✓ Original CRS: {gdf.crs}")

    gdf = gdf[gdf.geometry.notna()]
    gdf = gdf[~gdf.geometry.is_empty]

    if gdf.empty:
        raise ValueError(
            "The AOI contains no valid geometries."
        )

    gdf["geometry"] = gdf.geometry.make_valid()

    gdf = gdf[gdf.geometry.notna()]
    gdf = gdf[~gdf.geometry.is_empty]

    try:

        geometry = gdf.geometry.union_all()

    except AttributeError:

        geometry = gdf.geometry.unary_union

    if geometry.is_empty:
        raise ValueError(
            "The resulting geometry is empty."
        )

    if not geometry.is_valid:
        geometry = geometry.buffer(0)

    geometry = gpd.GeoSeries(
        [geometry],
        crs=gdf.crs
    ).to_crs(
        GEOGRAPHIC_CRS
    ).iloc[0]

    if not geometry.is_valid:
        geometry = geometry.buffer(0)

    print("✓ AOI converted to EPSG:4326.")
    print(f"✓ Final type: {geometry.geom_type}")
    print(f"✓ Valid geometry: {geometry.is_valid}")

    return geometry


def clean_rings(geometry):

    if geometry.geom_type == "Polygon":

        exterior = list(
            geometry.exterior.coords
        )

        if len(exterior) < 4:
            return None

        valid_interiors = []

        for interior in geometry.interiors:

            coords = list(
                interior.coords
            )

            if len(coords) >= 4:

                valid_interiors.append(
                    coords
                )

        return Polygon(
            exterior,
            valid_interiors
        )

    elif geometry.geom_type == "MultiPolygon":

        polygons = []

        for polygon in geometry.geoms:

            cleaned = clean_rings(
                polygon
            )

            if (
                cleaned is not None
                and not cleaned.is_empty
            ):

                polygons.append(
                    cleaned
                )

        if not polygons:
            return None

        return MultiPolygon(
            polygons
        )

    return geometry


def create_gee_roi(geometry):

    print(
        "🌎 Converting AOI to Earth Engine..."
    )

    geometry = clean_rings(
        geometry
    )

    if (
        geometry is None
        or geometry.is_empty
    ):

        raise ValueError(
            "The geometry became empty after "
            "cleaning its rings."
        )

    if not geometry.is_valid:

        geometry = geometry.buffer(0)

    geojson = geometry.__geo_interface__

    print(
        f"Geometry type: {geojson['type']}"
    )

    roi = ee.Geometry(
        geojson
    )

    print(
        "✓ AOI loaded successfully "
        "into Earth Engine."
    )

    return roi


def create_search_area(
    roi,
    margin_km
):

    print(
        f"📐 Applying search margin: "
        f"{margin_km} km"
    )

    search_area = roi.buffer(
        margin_km * 1000
    )

    search_area = search_area.simplify(
        100
    )

    print(
        "✓ Search area created."
    )

    return search_area



# SENTINEL-2
def mask_s2(img):

    scl = img.select(
        "SCL"
    )

    mask = (
        scl.eq(4)
        .Or(scl.eq(5))
        .Or(scl.eq(6))
        .Or(scl.eq(7))
    )

    return img.updateMask(
        mask
    )


def get_sentinel2(
    search_area,
    start_date,
    end_date
):

    collection = (
        ee.ImageCollection(
            "COPERNICUS/S2_SR_HARMONIZED"
        )
        .filterBounds(
            search_area
        )
        .filterDate(
            start_date,
            end_date
        )
        .filter(
            ee.Filter.lt(
                "CLOUDY_PIXEL_PERCENTAGE",
                80
            )
        )
        .sort(
            "CLOUDY_PIXEL_PERCENTAGE",
            True
        )
    )

    count = (
        collection
        .size()
        .getInfo()
    )

    print(
        f"\nSentinel-2:"
        f" {count} scenes found."
    )

    if count == 0:

        print(
            "⚠ Sentinel-2 skipped: "
            "no scenes were found."
        )

        return None

    image = collection.first()

    image = mask_s2(
        image
    )

    date_value = (
        image
        .date()
        .format("YYYY-MM-dd")
        .getInfo()
    )

    cloud_cover = (
        image
        .get(
            "CLOUDY_PIXEL_PERCENTAGE"
        )
        .getInfo()
    )

    print(
        f"✓ Selected Sentinel-2 scene: "
        f"{date_value}"
    )

    print(
        f"✓ Reported cloud cover: "
        f"{cloud_cover:.2f}%"
    )

    return image



# DEM
def get_dem(search_area):

    dem = (
        ee.ImageCollection(
            "COPERNICUS/DEM/GLO30"
        )
        .select(
            "DEM"
        )
        .mosaic()
        .clip(
            search_area
        )
    )

    return dem



# WORLDCOVER
def get_worldcover(search_area):

    worldcover = (
        ee.ImageCollection(
            "ESA/WorldCover/v200"
        )
        .first()
        .clip(
            search_area
        )
    )

    return worldcover



# SENTINEL-1
def get_sentinel1(
    search_area,
    start_date,
    end_date,
    polarization
):

    collection = (
        ee.ImageCollection(
            "COPERNICUS/S1_GRD"
        )
        .filterBounds(
            search_area
        )
        .filterDate(
            start_date,
            end_date
        )
        .filter(
            ee.Filter.eq(
                "instrumentMode",
                "IW"
            )
        )
        .filter(
            ee.Filter.listContains(
                "transmitterReceiverPolarisation",
                polarization
            )
        )
        .select(
            polarization
        )
        .sort(
            "system:time_start",
            True
        )
    )

    count = (
        collection
        .size()
        .getInfo()
    )

    print(
        f"\nSentinel-1 {polarization}: "
        f"{count} scenes found."
    )

    if count == 0:

        print(
            f"⚠ Sentinel-1 {polarization} skipped: "
            "no scenes were found."
        )

        return None

    image = collection.first()

    date_value = (
        image
        .date()
        .format("YYYY-MM-dd")
        .getInfo()
    )

    print(
        f"✓ Sentinel-1 scene {polarization} "
        f"selected: {date_value}"
    )

    return image



# DYNAMIC WORLD
def get_dynamic_world(
    search_area,
    start_date,
    end_date
):

    collection = (
        ee.ImageCollection(
            "GOOGLE/DYNAMICWORLD/V1"
        )
        .filterBounds(
            search_area
        )
        .filterDate(
            start_date,
            end_date
        )
        .select(
            "label"
        )
        .sort(
            "system:time_start",
            True
        )
    )

    count = (
        collection
        .size()
        .getInfo()
    )

    print(
        f"\nDynamic World:"
        f" {count} scenes found."
    )

    if count == 0:

        print(
            "⚠ Dynamic World skipped: "
            "no scenes were found."
        )

        return None

    image = collection.first()

    date_value = (
        image
        .date()
        .format("YYYY-MM-dd")
        .getInfo()
    )

    print(
        f"✓ Selected Dynamic World scene: "
        f"{date_value}"
    )

    return image



# JRC GLOBAL SURFACE WATER
def get_jrc_water(search_area):

    water = (
        ee.Image(
            "JRC/GSW1_4/GlobalSurfaceWater"
        )
        .clip(
            search_area
        )
        .toInt16()
    )

    return water



# MODIS LAND SURFACE TEMPERATURE
def get_lst(
    search_area,
    start_date,
    end_date
):

    collection = (
        ee.ImageCollection(
            "MODIS/061/MOD11A1"
        )
        .filterBounds(
            search_area
        )
        .filterDate(
            start_date,
            end_date
        )
        .select(
            "LST_Day_1km"
        )
        .sort(
            "system:time_start",
            True
        )
    )

    count = (
        collection
        .size()
        .getInfo()
    )

    print(
        f"\nMODIS LST:"
        f" {count} scenes found."
    )

    if count == 0:

        print(
            "⚠ MODIS LST skipped: "
            "no images were found."
        )

        return None

    image = collection.first()

    date_value = (
        image
        .date()
        .format("YYYY-MM-dd")
        .getInfo()
    )

    print(
        f"✓ Selected MODIS LST scene: "
        f"{date_value}"
    )

    return image



# CHIRPS PRECIPITATION
def get_chirps(
    search_area,
    start_date,
    end_date
):

    chirps = (
        ee.ImageCollection(
            "UCSB-CHC/CHIRPS/V3/DAILY_RNL"
        )
        .filterBounds(
            search_area
        )
        .filterDate(
            start_date,
            end_date
        )
        .select(
            "precipitation"
        )
        .sum()
        .clip(
            search_area
        )
    )

    return chirps



# MODIS EVAPOTRANSPIRATION
def get_et(
    search_area,
    start_date,
    end_date
):

    collection = (
        ee.ImageCollection(
            "MODIS/061/MOD16A2"
        )
        .filterBounds(
            search_area
        )
        .filterDate(
            start_date,
            end_date
        )
        .select(
            "ET"
        )
        .sort(
            "system:time_start",
            True
        )
    )

    count = (
        collection
        .size()
        .getInfo()
    )

    print(
        f"\nMODIS ET:"
        f" {count} scenes found."
    )

    if count == 0:

        print(
            "⚠ MODIS ET skipped: "
            "no data was found."
        )

        return None

    image = collection.first()

    date_value = (
        image
        .date()
        .format("YYYY-MM-dd")
        .getInfo()
    )

    print(
        f"✓ Selected MODIS ET scene: "
        f"{date_value}"
    )

    return image



# GLOBAL FOREST CANOPY HEIGHT
def get_canopy_height(search_area):

    canopy_height = (
        ee.Image(
            "NASA/JPL/global_forest_canopy_height_2005"
        )
        .select(
            "1"
        )
        .clip(
            search_area
        )
    )

    return canopy_height



# CREATE PRODUCTS
def create_products(
    selected,
    search_area,
    start_date,
    end_date
):

    products = {}


    required_ids = set(
        selected
    )

    for number in selected:

        dependencies = DATASETS[
            number
        ][
            "dependencies"
        ]

        required_ids.update(
            dependencies
        )


    needs_s2 = any(
        DATASETS[number]["type"]
        in [
            "sentinel2",
            "sentinel2_ndvi",
            "sentinel2_ndbi",
            "sentinel2_ndwi",
        ]
        for number in required_ids
    )

    s2_image = None

    if needs_s2:

        print(
            "\nProcessing Sentinel-2..."
        )

        try:

            s2_image = get_sentinel2(
                search_area,
                start_date,
                end_date
            )

            if s2_image is not None:

                print(
                    "✓ Sentinel-2 processed."
                )

        except Exception as e:

            print(
                "⚠ Sentinel-2 skipped due to error:"
            )

            print(e)


    needs_dem = (
        5 in required_ids
    )

    dem = None

    if needs_dem:

        print(
            "\nProcessing Copernicus GLO-30..."
        )

        try:

            dem = get_dem(
                search_area
            )

            print(
                "✓ DEM processed."
            )

        except Exception as e:

            print(
                "⚠ DEM skipped due to error:"
            )

            print(e)


    needs_worldcover = any(
        DATASETS[number]["type"]
        == "worldcover"
        for number in selected
    )

    worldcover = None

    if needs_worldcover:

        print(
            "\nProcessing ESA WorldCover..."
        )

        try:

            worldcover = get_worldcover(
                search_area
            )

            print(
                "✓ WorldCover processed."
            )

        except Exception as e:

            print(
                "⚠ WorldCover skipped due to error:"
            )

            print(e)


    needs_s1 = any(
        DATASETS[number]["type"]
        in [
            "sentinel1_vv",
            "sentinel1_vh",
        ]
        for number in selected
    )

    sentinel1_vv = None
    sentinel1_vh = None

    if needs_s1:

        if 7 in selected:

            print(
                "\nProcessing Sentinel-1 VV..."
            )

            try:

                sentinel1_vv = get_sentinel1(
                    search_area,
                    start_date,
                    end_date,
                    "VV"
                )

                if sentinel1_vv is not None:

                    print(
                        "✓ Sentinel-1 VV processed."
                    )

            except Exception as e:

                print(
                    "⚠ Sentinel-1 VV skipped due to error:"
                )

                print(e)

        if 8 in selected:

            print(
                "\nProcessing Sentinel-1 VH..."
            )

            try:

                sentinel1_vh = get_sentinel1(
                    search_area,
                    start_date,
                    end_date,
                    "VH"
                )

                if sentinel1_vh is not None:

                    print(
                        "✓ Sentinel-1 VH processed."
                    )

            except Exception as e:

                print(
                    "⚠ Sentinel-1 VH skipped due to error:"
                )

                print(e)


    dynamic_world = None

    if 9 in selected:

        print(
            "\nProcessing Dynamic World..."
        )

        try:

            dynamic_world = get_dynamic_world(
                search_area,
                start_date,
                end_date
            )

            if dynamic_world is not None:

                print(
                    "✓ Dynamic World processed."
                )

        except Exception as e:

            print(
                "⚠ Dynamic World skipped due to error:"
            )

            print(e)


    jrc_water = None

    if 10 in selected:

        print(
            "\nProcessing JRC Global Surface Water..."
        )

        try:

            jrc_water = get_jrc_water(
                search_area
            )

            print(
                "✓ JRC Global Surface Water processed."
            )

        except Exception as e:

            print(
                "⚠ JRC Global Surface Water skipped due to error:"
            )

            print(e)


    lst = None

    if 11 in selected:

        print(
            "\nProcessing MODIS Land Surface Temperature..."
        )

        try:

            lst = get_lst(
                search_area,
                start_date,
                end_date
            )

            if lst is not None:

                print(
                    "✓ MODIS LST processed."
                )

        except Exception as e:

            print(
                "⚠ MODIS LST skipped due to error:"
            )

            print(e)


    chirps = None

    if 12 in selected:

        print(
            "\nProcessing CHIRPS..."
        )

        try:

            chirps = get_chirps(
                search_area,
                start_date,
                end_date
            )

            if chirps is not None:

                print(
                    "✓ CHIRPS processed."
                )

        except Exception as e:

            print(
                "⚠ CHIRPS skipped due to error:"
            )

            print(e)


    et = None

    if 13 in selected:

        print(
            "\nProcessing MODIS Evapotranspiration..."
        )

        try:

            et = get_et(
                search_area,
                start_date,
                end_date
            )

            if et is not None:

                print(
                    "✓ MODIS ET processed."
                )

        except Exception as e:

            print(
                "⚠ MODIS ET skipped due to error:"
            )

            print(e)


    canopy_height = None

    if 14 in selected:

        print(
            "\nProcessing Global Forest Canopy Height..."
        )

        try:

            canopy_height = get_canopy_height(
                search_area
            )

            print(
                "✓ Global Forest Canopy Height processed."
            )

        except Exception as e:

            print(
                "⚠ Global Forest Canopy Height skipped due to error:"
            )

            print(e)


    for number in selected:

        type = DATASETS[
            number
        ][
            "type"
        ]


        if type == "sentinel2":

            if s2_image is not None:

                products[number] = (
                    s2_image.visualize(
                        bands=[
                            "B4",
                            "B3",
                            "B2"
                        ],
                        min=200,
                        max=3500
                    )
                )

            else:

                print(
                    "⚠ Sentinel-2 RGB skipped: "
                    "no scenes were found."
                )


        elif type == "sentinel2_ndvi":

            if s2_image is not None:

                products[number] = (
                    s2_image
                    .normalizedDifference(
                        [
                            "B8",
                            "B4"
                        ]
                    )
                    .rename(
                        "NDVI"
                    )
                )

            else:

                print(
                    "⚠ NDVI skipped: "
                    "no Sentinel-2 scenes were found."
                )


        elif type == "sentinel2_ndbi":

            if s2_image is not None:

                products[number] = (
                    s2_image
                    .normalizedDifference(
                        [
                            "B11",
                            "B8"
                        ]
                    )
                    .rename(
                        "NDBI"
                    )
                )

            else:

                print(
                    "⚠ NDBI skipped: "
                    "no Sentinel-2 scenes were found."
                )


        elif type == "sentinel2_ndwi":

            if s2_image is not None:

                products[number] = (
                    s2_image
                    .normalizedDifference(
                        [
                            "B3",
                            "B8"
                        ]
                    )
                    .rename(
                        "NDWI"
                    )
                )

            else:

                print(
                    "⚠ NDWI skipped: "
                    "no Sentinel-2 scenes were found."
                )


        elif type == "dem":

            if dem is not None:

                products[number] = dem


        elif type == "worldcover":

            if worldcover is not None:

                products[number] = worldcover


        elif type == "sentinel1_vv":

            if sentinel1_vv is not None:

                products[number] = sentinel1_vv

            else:

                print(
                    "⚠ Sentinel-1 VV skipped: "
                    "no hay data disponibles."
                )


        elif type == "sentinel1_vh":

            if sentinel1_vh is not None:

                products[number] = sentinel1_vh

            else:

                print(
                    "⚠ Sentinel-1 VH skipped: "
                    "no hay data disponibles."
                )


        elif type == "dynamic_world":

            if dynamic_world is not None:

                products[number] = dynamic_world

            else:

                print(
                    "⚠ Dynamic World skipped: "
                    "no hay data disponibles."
                )


        elif type == "jrc_water":

            if jrc_water is not None:

                products[number] = jrc_water.toInt16()


        elif type == "lst":

            if lst is not None:

                products[number] = lst

            else:

                print(
                    "⚠ MODIS LST skipped: "
                    "no hay data disponibles."
                )


        elif type == "chirps":

            if chirps is not None:

                products[number] = chirps

            else:

                print(
                    "⚠ CHIRPS skipped: "
                    "no hay data disponibles."
                )


        elif type == "et":

            if et is not None:

                products[number] = et

            else:

                print(
                    "⚠ MODIS ET skipped: "
                    "no hay data disponibles."
                )


        elif type == "canopy_height":

            if canopy_height is not None:

                products[number] = canopy_height

            else:

                print(
                    "⚠ Canopy Height skipped: "
                    "no hay data disponibles."
                )

    return products



# DATASET SELECTION
def show_datasets():

    print(
        "\n" + "=" * 70
    )

    print(
        "AVAILABLE DATASETS"
    )

    print(
        "=" * 70
    )

    for number, data in DATASETS.items():

        print(
            f"{number:>2}. "
            f"{data['name']}"
            f" — {data['description']}"
        )


def get_selection():

    show_datasets()

    while True:

        input_value = input(
            "\nSelect datasets "
            "(example: 1,2,5,6): "
        ).strip()

        try:

            numbers = [
                int(x.strip())
                for x in input_value.split(",")
            ]

        except ValueError:

            print(
                "⚠ Invalid format."
            )

            continue

        numbers = list(
            dict.fromkeys(
                numbers
            )
        )

        invalid_numbers = [
            number
            for number in numbers
            if number not in DATASETS
        ]

        if invalid_numbers:

            print(
                "⚠ Invalid options:"
                f" {invalid_numbers}"
            )

            continue

        if not numbers:

            print(
                "⚠ You must select "
                "at least one dataset."
            )

            continue

        return numbers



# FILE NAMES
def export_name(
    number,
    area_name
):

    names = {

        1: f"{area_name}_RGB",
        2: f"{area_name}_NDVI",
        3: f"{area_name}_NDBI",
        4: f"{area_name}_NDWI",
        5: f"{area_name}_DEM",
        6: f"{area_name}_WorldCover",
        7: f"{area_name}_Sentinel1_VV",
        8: f"{area_name}_Sentinel1_VH",
        9: f"{area_name}_DynamicWorld",
        10: f"{area_name}_JRC_SurfaceWater",
        11: f"{area_name}_LST",
        12: f"{area_name}_CHIRPS",
        13: f"{area_name}_ET",
        14: f"{area_name}_CanopyHeight",

    }

    return names.get(
        number,
        f"{area_name}_dataset_{number}"
    )


def export_scale(number):

    scales = {

        1: 10,
        2: 10,
        3: 20,
        4: 10,
        5: 30,
        6: 10,
        7: 10,
        8: 10,
        9: 10,
        10: 30,
        11: 1000,
        12: 5566,
        13: 500,
        14: 928,

    }

    return scales.get(
        number,
        10
    )



# EXPORT TO GOOGLE DRIVE
def export_products(
    products,
    selected,
    roi,
    area_name,
    drive_folder
):

    print(
        "\n" + "=" * 70
    )

    print(
        "EXPORTS"
    )

    print(
        "=" * 70
    )

    tasks = []

    for number in selected:

        if number not in products:

            print(
                f"\n⚠ Dataset skipped: "
                f"{DATASETS[number]['name']}"
            )

            continue

        image = products[
            number
        ]

        name = export_name(
            number,
            area_name
        )

        scale = export_scale(
            number
        )

        print(
            f"\nPreparing: {name}"
        )

        try:

            task = (
                ee.batch.Export.image.toDrive(
                    image=image,
                    description=name,
                    folder=drive_folder,
                    fileNamePrefix=name,
                    region=roi,
                    scale=scale,
                    crs=EXPORT_CRS,
                    maxPixels=1e13
                )
            )

            task.start()

            tasks.append(
                task
            )

            print(
                f"✓ Task submitted: "
                f"{name}"
            )

        except Exception as e:

            print(
                f"✗ Error exporting "
                f"{name}:"
            )

            print(e)

    return tasks



# SAVE LOCAL SUMMARY
def save_summary(
    area_name,
    project_id,
    project_link,
    aoi_path,
    start_date,
    end_date,
    margin_km,
    selected,
    drive_folder
):

    output_folder = (
        Path("data")
        / "outputs"
        / area_name
        / "GEE"
    )

    output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    path = (
        output_folder
        / "GEE_CONFIGURATION.txt"
    )

    lines = [

        "GEE SEARCH CONFIGURATION",

        "=" * 50,

        "",

        f"Study area: {area_name}",

        f"AOI: {aoi_path}",

        f"GEE project: {project_id}",

        f"GEE link: {project_link}",

        f"Start date: {start_date}",

        f"End date: {end_date}",

        f"Margin: {margin_km} km",

        "Temporal method: single-scene selection",

        "Sentinel-2: scene with lowest cloud cover",

        "Other temporal datasets: first available scene",

        f"Drive folder: {drive_folder}",

        "",

        "REQUESTED DATASETS",

        "-" * 50,

    ]

    for number in selected:

        lines.append(
            f"{number}. "
            f"{DATASETS[number]['name']}"
        )

    path.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    return path



# SHOW TASKS
def show_tasks():

    print(
        "\n" + "=" * 70
    )

    print(
        "TASK MANAGER"
    )

    print(
        "=" * 70
    )

    print(
        "You can review exports here:"
    )

    print(
        "https://code.earthengine.google.com/tasks"
    )

    print(
        "\nLatest tasks:"
    )

    try:

        tasks = ee.batch.Task.list()

        for task in tasks[:10]:

            description = (
                task.config.get(
                    "description",
                    "Unnamed"
                )
            )

            print(
                f"[{task.state}] "
                f"{description}"
            )

    except Exception as e:

        print(
            "Unable to query "
            "las tasks:"
        )

        print(e)



# MAIN PROGRAM
def main():

    print(
        "\n" + "=" * 70
    )

    print(
        "GOOGLE EARTH ENGINE DATASET SEARCHER"
    )

    print(
        "=" * 70
    )


    project_id = get_project()

    project_link = build_project_link(
        project_id
    )

    print("\n🔗 GEE project:")
    print(project_link)


    initialize_earth_engine(
        project_id
    )


    aoi_path = get_text(
        "\nStudy area path"
    )

    aoi_path = Path(
        aoi_path
    )

    if not aoi_path.exists():

        raise FileNotFoundError(
            f"File does not exist:"
            f" {aoi_path}"
        )

    area_name = (
        aoi_path.stem
    )


    geometry = load_area(
        aoi_path
    )

    roi = create_gee_roi(
        geometry
    )

    print(
        "✓ Study area loaded."
    )


    start_date = get_text(
        "\nStart date",
        "2025-01-01"
    )

    end_date = get_text(
        "End date",
        "2025-12-31"
    )


    margin_km = get_float(
        "\nMargin around the area (km)",
        DEFAULT_MARGIN_KM
    )

    search_area = (
        create_search_area(
            roi,
            margin_km
        )
    )

    print(
        f"✓ Search area created "
        f"with a margin of {margin_km} km."
    )


    selected = (
        get_selection()
    )


    default_folder = (
        f"GEE_Busqueda_{area_name}"
    )

    drive_folder = get_text(
        "\nGoogle Drive folder",
        default_folder
    )


    print(
        "\n" + "=" * 70
    )

    print(
        "CONFIGURATION"
    )

    print(
        "=" * 70
    )

    print(
        f"Area:             {area_name}"
    )

    print(
        f"GEE project:     {project_id}"
    )

    print(
        f"Start:           {start_date}"
    )

    print(
        f"End:              {end_date}"
    )

    print(
        f"Margin:           {margin_km} km"
    )

    print(
        f"Drive:             {drive_folder}"
    )

    print(
        "\nTemporal method:"
    )

    print(
        "  • Sentinel-2 → scene with lowest cloud cover"
    )

    print(
        "  • Other temporal datasets → first scene"
    )

    print(
        "  • No median/mode composites are performed"
    )

    print(
        "\nProducts:"
    )

    for number in selected:

        print(
            f"  {number}. "
            f"{DATASETS[number]['name']}"
        )


    print(
        "\n" + "=" * 70
    )

    print(
        "PROCESSING"
    )

    print(
        "=" * 70
    )

    products = create_products(
        selected,
        search_area,
        start_date,
        end_date
    )


    tasks = export_products(
        products,
        selected,
        roi,
        area_name,
        drive_folder
    )


    config_path = save_summary(
        area_name,
        project_id,
        project_link,
        aoi_path,
        start_date,
        end_date,
        margin_km,
        selected,
        drive_folder
    )


    print(
        "\n" + "=" * 70
    )

    print(
        "RESULT"
    )

    print(
        "=" * 70
    )

    print(
        f"\n✓ {len(tasks)} "
        f"exports submitted to GEE."
    )

    print(
        "\nGoogle Drive:"
    )

    print(
        drive_folder
    )

    print(
        "\nProject used:"
    )

    print(
        project_link
    )

    print(
        "\nConfiguration saved to:"
    )

    print(
        config_path
    )

    show_tasks()



# RUN
if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print(
            "\n\nProcess cancelled."
        )

    except Exception as e:

        print(
            "\n\n❌ ERROR:"
        )

        print(e)
