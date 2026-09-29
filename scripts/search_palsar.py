import sys

from pathlib import Path

import asf_search as asf

import geopandas as gpd

import pandas as pd

from shapely.geometry import shape

from shapely import make_valid


# CONFIGURATION

WORKING_CRS = "EPSG:32719"

GEOGRAPHIC_CRS = "EPSG:4326"

TARGET_COVERAGE = 100.0

DATA_DIR = Path("data")


# LOAD BOUNDARY

def load_boundary(path):

    print(f"\nReading boundary: {path}")

    gdf = gpd.read_file(path)

    if gdf.empty:

        raise ValueError(
            "The boundary file contains no geometries."
        )

    if gdf.crs is None:

        raise ValueError(
            "The boundary file has no defined CRS."
        )

    geometry = gdf.geometry.union_all()

    geometry = make_valid(geometry)

    boundary = gpd.GeoDataFrame(
        {"name": ["study_area"]},
        geometry=[geometry],
        crs=gdf.crs
    )

    boundary = boundary.to_crs(GEOGRAPHIC_CRS)

    return boundary


# SEARCH SCENES

def search_scenes(boundary):

    minx, miny, maxx, maxy = boundary.total_bounds

    bbox = (
        f"POLYGON(("
        f"{minx} {miny}, "
        f"{maxx} {miny}, "
        f"{maxx} {maxy}, "
        f"{minx} {maxy}, "
        f"{minx} {miny}"
        f"))"
    )

    print("\nSearching for ALOS PALSAR RTC_HI_RES scenes...")

    print(
        f"BBOX: "
        f"{minx:.4f}, {miny:.4f}, "
        f"{maxx:.4f}, {maxy:.4f}"
    )

    results = asf.search(
        dataset=asf.DATASET.ALOS_PALSAR,
        intersectsWith=bbox,
        processingLevel="RTC_HI_RES",
    )

    print(f"Scenes found: {len(results)}")

    return results


# GET DOWNLOAD URL

def get_download_url(result):

    properties = getattr(
        result,
        "properties",
        {}
    )

    possible_fields = [
        "url",
        "downloadUrl",
        "download_url",
        "browse",
        "productUrl",
        "product_url",
    ]

    for field in possible_fields:

        value = properties.get(field)

        if isinstance(value, str):

            if value.startswith("http"):

                return value

    possible_attributes = [
        "url",
        "download_url",
        "downloadUrl",
        "product_url",
        "productUrl",
    ]

    for attribute in possible_attributes:

        value = getattr(
            result,
            attribute,
            None
        )

        if isinstance(value, str):

            if value.startswith("http"):

                return value

    return None


# BUILD SCENE GEODATAFRAME

def build_scene_gdf(results):

    records = []

    for result in results:

        records.append({
            "scene_name": result.properties.get(
                "sceneName"
            ),

            "date": result.properties.get(
                "startTime"
            ),

            "download_url": get_download_url(
                result
            ),

            "geometry": shape(
                result.geometry
            ),
        })

    if not records:

        return gpd.GeoDataFrame(
            columns=[
                "scene_name",
                "date",
                "download_url",
                "geometry"
            ],
            geometry="geometry",
            crs=GEOGRAPHIC_CRS
        )

    scenes = gpd.GeoDataFrame(
        records,
        geometry="geometry",
        crs=GEOGRAPHIC_CRS
    )

    scenes["geometry"] = scenes.geometry.apply(
        make_valid
    )

    return scenes


# CALCULATE INDIVIDUAL COVERAGE

def calculate_coverage(boundary, scenes):

    boundary_utm = boundary.to_crs(WORKING_CRS)

    scenes_utm = scenes.to_crs(WORKING_CRS)

    boundary_geometry = make_valid(
        boundary_utm.geometry.iloc[0]
    )

    boundary_area = boundary_geometry.area

    results = []

    for _, scene in scenes_utm.iterrows():

        scene_geometry = make_valid(
            scene.geometry
        )

        try:

            intersection = scene_geometry.intersection(
                boundary_geometry
            )

        except Exception:

            intersection = (
                scene_geometry.buffer(0)
                .intersection(
                    boundary_geometry.buffer(0)
                )
            )

        if intersection.is_empty:

            intersection_area = 0

        else:

            intersection_area = intersection.area

        coverage = (
            intersection_area /
            boundary_area
        ) * 100

        results.append({
            "scene_name": scene["scene_name"],

            "date": scene["date"],

            "download_url": scene["download_url"],

            "area_km2": (
                intersection_area /
                1_000_000
            ),

            "individual_coverage": coverage,

            "geometry": scene.geometry,
        })

    scenes_coverage = gpd.GeoDataFrame(
        results,
        geometry="geometry",
        crs=WORKING_CRS
    )

    scenes_coverage = (
        scenes_coverage
        .sort_values(
            "individual_coverage",
            ascending=False
        )
        .reset_index(drop=True)
    )

    return boundary_utm, scenes_coverage


# SELECT SCENES

def select_scenes(boundary_utm, scenes):

    boundary_geometry = make_valid(
        boundary_utm.geometry.iloc[0]
    )

    total_area = boundary_geometry.area

    current_coverage = None

    selected_scenes = []

    remaining = scenes.copy()

    print(
        "\n========================================"
    )

    print(
        "SCENE SELECTION"
    )

    print(
        "========================================"
    )

    number = 1

    while not remaining.empty:

        best_index = None

        best_contribution = 0

        best_new_geometry = None

        for index, scene in remaining.iterrows():

            scene_geometry = make_valid(
                scene.geometry
            )

            try:

                scene_geometry = (
                    scene_geometry.intersection(
                        boundary_geometry
                    )
                )

            except Exception:

                scene_geometry = (
                    scene_geometry
                    .buffer(0)
                    .intersection(
                        boundary_geometry.buffer(0)
                    )
                )

            if scene_geometry.is_empty:

                continue

            if current_coverage is None:

                new_geometry = scene_geometry

            else:

                try:

                    new_geometry = (
                        scene_geometry.difference(
                            current_coverage
                        )
                    )

                except Exception:

                    new_geometry = (
                        scene_geometry
                        .buffer(0)
                        .difference(
                            current_coverage.buffer(0)
                        )
                    )

            contribution = new_geometry.area

            if contribution > best_contribution:

                best_contribution = contribution

                best_index = index

                best_new_geometry = new_geometry

        if (
            best_index is None
            or best_contribution <= 0
        ):

            break

        scene = remaining.loc[
            best_index
        ]

        if current_coverage is None:

            current_coverage = (
                best_new_geometry
            )

        else:

            try:

                current_coverage = (
                    current_coverage.union(
                        best_new_geometry
                    )
                )

            except Exception:

                current_coverage = (
                    current_coverage
                    .buffer(0)
                    .union(
                        best_new_geometry.buffer(0)
                    )
                )

        current_coverage = make_valid(
            current_coverage
        )

        accumulated_coverage = (
            current_coverage.area /
            total_area
        ) * 100

        contribution_percentage = (
            best_contribution /
            total_area
        ) * 100

        date = pd.to_datetime(
            scene["date"],
            errors="coerce"
        )

        if pd.notna(date):

            date_text = (
                date.strftime("%Y-%m-%d")
            )

        else:

            date_text = str(
                scene["date"]
            )

        print(
            f"{number}. "
            f"{scene['scene_name']}"
        )

        print(
            f"   Date:          "
            f"{date_text}"
        )

        print(
            f"   Coverage:      "
            f"{scene['individual_coverage']:.2f}%"
        )

        print(
            f"   Contribution:  "
            f"{contribution_percentage:.2f}%"
        )

        print(
            f"   Accumulated:   "
            f"{accumulated_coverage:.2f}%"
        )

        print()

        selected_scenes.append({

            "scene_name": (
                scene["scene_name"]
            ),

            "date": (
                scene["date"]
            ),

            "download_url": (
                scene["download_url"]
            ),

            "individual_coverage": (
                scene[
                    "individual_coverage"
                ]
            ),

            "new_contribution": (
                contribution_percentage
            ),

            "accumulated_coverage": (
                accumulated_coverage
            ),

        })

        remaining = remaining.drop(
            index=best_index
        )

        number += 1

        if (
            accumulated_coverage
            >= TARGET_COVERAGE - 0.000001
        ):

            break

    return (
        selected_scenes,
        current_coverage
    )


# GENERATE DOWNLOAD MARKDOWN

def generate_download_markdown(
    selected_scenes,
    area_name,
    final_coverage,
    output_path
):

    lines = []

    lines.append(
        f"# ALOS PALSAR Downloads\n"
    )

    lines.append(
        f"**Area:** `{area_name}`\n"
    )

    lines.append(
        f"**Product:** `ALOS PALSAR RTC_HI_RES`\n"
    )

    lines.append(
        f"**Selected coverage:** "
        f"`{final_coverage:.6f}%`\n"
    )

    lines.append(
        f"**Selected scenes:** "
        f"`{len(selected_scenes)}`\n"
    )

    lines.append("---\n")

    lines.append(
        "> This file contains the download links for "
        "the products selected by the script. "
        "The download is not performed automatically "
        "because ASF requires Earthdata authentication.\n"
    )

    lines.append("---\n")

    for number, scene in enumerate(
        selected_scenes,
        start=1
    ):

        date = pd.to_datetime(
            scene["date"],
            errors="coerce"
        )

        if pd.notna(date):

            date_text = (
                date.strftime("%Y-%m-%d")
            )

        else:

            date_text = str(
                scene["date"]
            )

        lines.append(
            f"## {number}. "
            f"{scene['scene_name']}\n"
        )

        lines.append(
            f"- **Date:** {date_text}"
        )

        lines.append(
            f"- **Individual coverage:** "
            f"{scene['individual_coverage']:.6f}%"
        )

        lines.append(
            f"- **New contribution:** "
            f"{scene['new_contribution']:.6f}%"
        )

        lines.append(
            f"- **Accumulated coverage:** "
            f"{scene['accumulated_coverage']:.6f}%"
        )

        url = scene.get(
            "download_url"
        )

        if url:

            lines.append(
                f"- **Download:** "
                f"[Open product in ASF]({url})"
            )

        else:

            lines.append(
                "- **Download:** "
                "URL not available in the ASF response."
            )

        lines.append("")

    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )


# SAVE RESULTS

def save_results(
    boundary_utm,
    scenes,
    selected_scenes,
    current_coverage,
    area_name
):

    output_folder = (
        DATA_DIR /
        area_name
    )

    output_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    selected_names = [
        scene["scene_name"]
        for scene in selected_scenes
    ]

    selected_scenes_gdf = scenes[
        scenes["scene_name"].isin(
            selected_names
        )
    ].copy()

    scenes_path = (
        output_folder /
        "selected_scenes.gpkg"
    )

    selected_scenes_gdf.to_file(
        scenes_path,
        layer="scenes",
        driver="GPKG"
    )

    boundary_geometry = make_valid(
        boundary_utm.geometry.iloc[0]
    )

    if current_coverage is None:

        uncovered_area = boundary_geometry

    else:

        coverage_geometry = make_valid(
            current_coverage
        )

        try:

            uncovered_area = (
                boundary_geometry.difference(
                    coverage_geometry
                )
            )

        except Exception:

            uncovered_area = (
                boundary_geometry
                .buffer(0)
                .difference(
                    coverage_geometry.buffer(0)
                )
            )

    uncovered_area = make_valid(
        uncovered_area
    )

    uncovered_gdf = gpd.GeoDataFrame(
        {
            "type": [
                "uncovered_area"
            ]
        },
        geometry=[
            uncovered_area
        ],
        crs=WORKING_CRS
    )

    uncovered_path = (
        output_folder /
        "uncovered_area.gpkg"
    )

    uncovered_gdf.to_file(
        uncovered_path,
        layer="uncovered",
        driver="GPKG"
    )

    df = pd.DataFrame(
        selected_scenes
    )

    df["individual_coverage"] = (
        df["individual_coverage"]
        .round(6)
    )

    df["new_contribution"] = (
        df["new_contribution"]
        .round(6)
    )

    df["accumulated_coverage"] = (
        df["accumulated_coverage"]
        .round(6)
    )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    csv_path = (
        output_folder /
        "selection.csv"
    )

    df.to_csv(
        csv_path,
        index=False,
        encoding="utf-8-sig"
    )

    final_coverage = (
        selected_scenes[-1][
            "accumulated_coverage"
        ]
    )

    markdown_path = (
        output_folder /
        "DOWNLOADS.md"
    )

    generate_download_markdown(
        selected_scenes=selected_scenes,
        area_name=area_name,
        final_coverage=final_coverage,
        output_path=markdown_path
    )

    return (
        scenes_path,
        uncovered_path,
        csv_path,
        markdown_path,
        output_folder
    )


# MAIN PROGRAM

def main():

    if len(sys.argv) < 2:

        print(
            "\nUsage:"
        )

        print(
            "python scripts/search_palsar.py "
            "path/to/boundary.gpkg"
        )

        sys.exit(1)

    boundary_path = Path(
        sys.argv[1]
    )

    if not boundary_path.exists():

        print(
            "\nERROR: file does not exist:"
        )

        print(
            f"{boundary_path}"
        )

        sys.exit(1)

    area_name = (
        boundary_path.stem
    )

    boundary = load_boundary(
        boundary_path
    )

    results = search_scenes(
        boundary
    )

    if not results:

        print(
            "\nNo scenes were found."
        )

        sys.exit(0)

    scenes = (
        build_scene_gdf(
            results
        )
    )

    boundary_utm, scenes = (
        calculate_coverage(
            boundary,
            scenes
        )
    )

    scenes = scenes[
        scenes[
            "individual_coverage"
        ] > 0
    ].copy()

    print(
        f"Scenes intersecting "
        f"the boundary: {len(scenes)}"
    )

    (
        selected_scenes,
        current_coverage
    ) = select_scenes(
        boundary_utm,
        scenes
    )

    if not selected_scenes:

        print(
            "\nIt was not possible to cover "
            "the area."
        )

        sys.exit(0)

    (
        scenes_path,
        uncovered_path,
        csv_path,
        markdown_path,
        output_folder
    ) = save_results(
        boundary_utm,
        scenes,
        selected_scenes,
        current_coverage,
        area_name
    )

    final_coverage = (
        selected_scenes[-1][
            "accumulated_coverage"
        ]
    )

    total_area = (
        boundary_utm
        .geometry
        .iloc[0]
        .area
    )

    uncovered_area = (
        total_area
        * (
            1 -
            final_coverage / 100
        )
    )

    print(
        "\n========================================"
    )

    print(
        "FINAL RESULT"
    )

    print(
        "========================================"
    )

    print(
        f"Area: {area_name}"
    )

    print(
        f"Selected scenes: "
        f"{len(selected_scenes)}"
    )

    print(
        f"Total coverage: "
        f"{final_coverage:.6f}%"
    )

    print(
        f"Uncovered area: "
        f"{uncovered_area / 1_000_000:.6f} km²"
    )

    print(
        "\nGenerated files:"
    )

    print(
        f"  {scenes_path}"
    )

    print(
        f"  {uncovered_path}"
    )

    print(
        f"  {csv_path}"
    )

    print(
        f"  {markdown_path}"
    )


# RUN

if __name__ == "__main__":

    main()
