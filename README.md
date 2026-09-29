# Geospatial Data Tools

A personal collection of Python tools for searching, selecting, processing, and preparing geospatial datasets from **Google Earth Engine (GEE)** and **Alaska Satellite Facility (ASF)**.

The project is designed to grow over time as new datasets, workflows, and tools become necessary.

The tools are mainly intended for geospatial analysis, remote sensing, geomatics, and research workflows where repetitive data acquisition and preparation can be automated.

---

# Installation

Clone the repository and navigate to the project directory:

```powershell
git clone <repository-url>
cd <repository-folder>
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
```

```powershell
.venv\Scripts\activate
```

Install the required dependencies:

```powershell
pip install -r requirements.txt
```

The required Python packages and their dependencies will be installed automatically.

---

# Requirements

* Python 3.x
* A Google Earth Engine account and accessible project for GEE tools
* An ASF account for ASF-based workflows

Python dependencies are listed in `requirements.txt`.

---

# Project Structure

```text
project/
│
├── scripts/
│   ├── search_gee.py
│   ├── search_gee_composite.py
│   ├── search_insar.py
│   └── search_palsar.py
│
├── data/
│   ├── inputs/
│   └── outputs/
│
├── requirements.txt
└── README.md
```

The `scripts/` directory contains the different acquisition and selection tools.

The `data/inputs/` directory can be used to store study-area boundaries, while generated results are stored under `data/outputs/`.

---

# Input Boundaries

The tools that work with an area of interest use **GeoPandas** to read the input boundary.

The boundary does not have to be a GeoPackage. Any vector format supported by the installed GeoPandas I/O engine can be used.

Common examples include:

* GeoPackage (`.gpkg`)
* Shapefile (`.shp`)
* GeoJSON (`.geojson`)
* Other GDAL/OGR-supported vector formats

Examples:

```text
path/to/your/boundary.gpkg
```

```text
path/to/your/boundary.shp
```

```text
path/to/your/boundary.geojson
```

The boundary must contain a valid coordinate reference system (CRS).

The tools internally handle the required reprojection for the different processing workflows.

---

# Tools

## 1. Sentinel-1 InSAR Scene Selector

### `search_insar.py`

This tool searches for **Sentinel-1 SLC IW** scenes through ASF and automatically selects the scenes required to maximize coverage of the study area.

The selection is performed independently for each acquisition date and orbital direction.

### Run a Search

From the project root:

```powershell
python scripts/search_insar.py path/to/your/boundary.gpkg --period 2026-03-01,2026-04-30
```

The boundary can be replaced with any supported vector format:

```powershell
python scripts/search_insar.py path/to/your/boundary.shp --period 2026-03-01,2026-04-30
```

### Specify a Different Period

```powershell
python scripts/search_insar.py path/to/your/boundary.gpkg --period 2026-01-01,2026-12-31
```

### Search Only Ascending Orbits

```powershell
python scripts/search_insar.py path/to/your/boundary.gpkg --period 2026-01-01,2026-12-31 --direction ASCENDING
```

### Search Only Descending Orbits

```powershell
python scripts/search_insar.py path/to/your/boundary.gpkg --period 2026-01-01,2026-12-31 --direction DESCENDING
```

### Results

Results are automatically organized under:

```text
data/outputs/<boundary_name>/
```

The generated files include:

* `sentinel1_scenes.gpkg` — selected Sentinel-1 scene footprints and metadata.
* `sentinel1_scenes.csv` — scene metadata.
* `SENTINEL1_DOWNLOADS.md` — coverage information by date and orbital direction, together with download links.

---

# 2. ALOS PALSAR Scene Selector

### `search_palsar.py`

This tool searches for **ALOS PALSAR RTC_HI_RES** products through ASF and automatically selects a combination of scenes to maximize coverage of the study area.

For each scene, the tool calculates the percentage of the study area covered.

It then uses a progressive selection process:

1. Calculate the coverage contributed by each available scene.
2. Select the scene that contributes the largest amount of new area.
3. Add its coverage to the accumulated area.
4. Repeat the process until the study area reaches 100% coverage or no additional coverage is available.

### Run a Search

From the project root:

```powershell
python scripts/search_palsar.py path/to/your/boundary.gpkg
```

For example, using a Shapefile:

```powershell
python scripts/search_palsar.py path/to/your/boundary.shp
```

### Results

Results are automatically saved under:

```text
data/outputs/<boundary_name>/
```

The generated files include:

* `selected_scenes.gpkg` — selected scenes used to cover the study area.
* `uncovered_area.gpkg` — area that could not be covered.
* `selection.csv` — scene selection and coverage contribution details.
* `DOWNLOADS.md` — download links for the selected ASF products.

The tool generates download links but does not automatically download the PALSAR products.

---

# 3. Google Earth Engine Dataset Searcher

The Google Earth Engine tools allow different datasets to be searched and prepared from a user-defined study area.

The tools use GeoPandas to read the study-area boundary and Google Earth Engine to search, process, and export the requested datasets.

Two versions are currently available:

* `search_gee.py` — single-scene or single-period processing.
* `search_gee_composite.py` — temporal composition of multiple images.

Both tools interact with the user through the terminal.

---

## 3.1 Single-Scene / Single-Period Search

### `search_gee.py`

This version is designed to work with a single selected image or period rather than creating a temporal composition from multiple dates.

The selection method depends on the dataset.

Current behavior includes:

* **Sentinel-2:** selects the image with the lowest cloud coverage.
* **Sentinel-1:** selects the first available image.
* **Dynamic World:** selects the first available image.
* **MODIS LST:** selects the first available image.
* **CHIRPS:** calculates accumulated precipitation over the selected period.
* **MODIS ET:** selects the first available image.
* **Non-temporal datasets:** such as DEM and WorldCover, are generated directly.

This mode is useful when the analysis requires a specific scene or period without creating a temporal composition.

### Run

From the project root:

```powershell
python scripts/search_gee.py
```

The script will request the required information interactively, including:

* Google Earth Engine project
* Study-area boundary
* Date range
* Search margin
* Datasets to export
* Google Drive output folder

The study-area boundary can be supplied using any vector format supported by GeoPandas.

---

## 3.2 Temporal Composition

### `search_gee_composite.py`

This version is designed to combine multiple images over a selected temporal period.

It can be used when a single satellite scene is not sufficient or when a temporal product is required.

The composition method depends on the dataset and processing configuration.

### Run

From the project root:

```powershell
python scripts/search_gee_composite.py
```

The script will request the processing configuration interactively, including:

* Google Earth Engine project
* Study area
* Temporal period
* Datasets

The resulting products are exported to Google Drive.

---

# Authentication

## Google Earth Engine

The GEE tools require a Google Earth Engine account and an accessible Google Cloud / Earth Engine project.

When prompted for the project, the tool can accept:

```text
my-project
```

or:

```text
projects/my-project
```

It can also process a Google Earth Engine project URL and extract the project ID automatically.

The exported products are sent to the Google Drive folder specified during execution.

Earth Engine export tasks can be monitored through the Earth Engine task manager.

## Alaska Satellite Facility

ASF-based tools require the appropriate ASF authentication credentials.

These tools use the `asf_search` Python package to search ASF products and generate the corresponding product information and download links.

---

# Output Organization

The tools organize generated results according to the name of the input study area.

A typical structure is:

```text
data/
│
├── inputs/
│   └── your_boundary.gpkg
│
└── outputs/
    └── your_boundary/
        ├── ...
        └── ...
```

This allows the same tools to be used with different study areas without modifying the source code.

---

# Workflow Philosophy

The main goal of this project is to automate repetitive geospatial data acquisition tasks.

Instead of manually searching for scenes, checking coverage, retrieving metadata, and preparing datasets through several different applications, the tools provide a reproducible command-line workflow.

The project is intentionally modular and will continue to grow as new datasets and workflows are needed.

Future tools may include additional:

* Satellite datasets
* DEM products
* Climate datasets
* Remote sensing products
* ASF search workflows
* Google Earth Engine datasets
* Spatial analysis utilities
* Automated preprocessing workflows

---

# Disclaimer

This is a personal project developed for learning, research, and practical geospatial workflows.

The tools depend on external services and datasets provided by organizations such as **Google Earth Engine** and **Alaska Satellite Facility**. Dataset availability, APIs, authentication requirements, and service behavior may change over time.

Always verify the original dataset documentation and licensing requirements before using the resulting data in a project or publication.
