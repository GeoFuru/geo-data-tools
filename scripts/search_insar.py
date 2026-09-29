from __future__ import annotations

import argparse

from datetime import datetime, timedelta

from pathlib import Path

import asf_search as asf

import geopandas as gpd

import pandas as pd

from shapely.geometry import shape

from shapely.validation import make_valid




# GENERAL CONFIGURATION

WORKING_CRS = "EPSG:32719"

GEOGRAPHIC_CRS = "EPSG:4326"

DATA_OUTPUTS = Path("data/outputs")

PRODUCT = asf.PRODUCT_TYPE.SLC

TARGET_COVERAGE = 99.999

MAX_SCENES_PER_DATE = 10




# ARGUMENTS

def parse_args():

    parser = argparse.ArgumentParser(

        description=(

            "Searches Sentinel-1 SLC over an AOI and selects, "

            "for each date and orbit direction, the smallest "

            "number of scenes required to maximize "

            "the spatial coverage of the AOI."

        )

    )

    parser.add_argument(

        "boundary",

        help="Path to the AOI vector file."

    )

    parser.add_argument(

        "--period",

        action="append",

        required=True,

        metavar="START,END",

        help=(

            "Time period to search. "

            "Can be repeated multiple times."

        )

    )

    parser.add_argument(

        "--direction",

        choices=[

            "ASCENDING",

            "DESCENDING",

        ],

        default=None,

        help=(

            "Limits the search to one orbit direction. "

            "By default, searches ASCENDING and DESCENDING."

        )

    )

    return parser.parse_args()




# PERIODS

def parse_periods(raw_periods):

    periods = []

    for period in raw_periods:

        try:

            start_raw, end_raw = (

                period.split(",", 1)

            )

            start = datetime.strptime(

                start_raw.strip(),

                "%Y-%m-%d",

            )

            end = datetime.strptime(

                end_raw.strip(),

                "%Y-%m-%d",

            )

        except ValueError:

            raise ValueError(

                f"Invalid period: '{period}'. "

                "Use YYYY-MM-DD,YYYY-MM-DD"

            )

        if start > end:

            raise ValueError(

                f"The start of the period is after "

                f"the end: {period}"

            )

        end = (

            end

            + timedelta(days=1)

            - timedelta(seconds=1)

        )

        periods.append(

            (start, end)

        )

    return periods




# AOI

def load_aoi(path):

    print(

        f"Reading boundary: {path}"

    )

    gdf = gpd.read_file(

        path

    )

    if gdf.empty:

        raise ValueError(

            "The boundary file is empty."

        )

    if gdf.crs is None:

        raise ValueError(

            "The boundary file has no defined CRS."

        )

    gdf["geometry"] = (

        gdf.geometry.apply(

            lambda geom:

                make_valid(geom)

                if geom is not None

                else geom

        )

    )

    geometry = (

        gdf.geometry

        .union_all()

    )

    if geometry.is_empty:

        raise ValueError(

            "The boundary geometry is empty."

        )

    return geometry, gdf.crs


def build_bbox_wkt(geometry):

    minx, miny, maxx, maxy = (

        geometry.bounds

    )

    return (

        "POLYGON(("

        f"{minx} {miny}, "

        f"{maxx} {miny}, "

        f"{maxx} {maxy}, "

        f"{minx} {maxy}, "

        f"{minx} {miny}"

        "))"

    )




# ASF SEARCH

def search_scenes(

    aoi_wkt,

    periods,

    direction,

):

    overall_start = min(

        period[0]

        for period in periods

    )

    overall_end = max(

        period[1]

        for period in periods

    )

    print()

    print(

        "Buscando scenes Sentinel-1 SLC..."

    )

    print(

        f"Window: "

        f"{overall_start:%Y-%m-%d} → "

        f"{overall_end:%Y-%m-%d}"

    )

    results = asf.geo_search(

        platform=[

            asf.PLATFORM.SENTINEL1

        ],

        processingLevel=[

            PRODUCT

        ],

        intersectsWith=aoi_wkt,

        start=overall_start.strftime(

            "%Y-%m-%d"

        ),

        end=overall_end.strftime(

            "%Y-%m-%d"

        ),

        maxResults=2500,

    )

    print(

        f"ASF results: "

        f"{len(results)}"

    )

    scenes = []

    for product in results:

        p = product.properties



        raw_date = p.get(

            "startTime"

        )

        if not raw_date:

            continue

        try:

            date_time = (

                datetime.fromisoformat(

                    raw_date.replace(

                        "Z",

                        "+00:00",

                    )

                )

                .replace(

                    tzinfo=None

                )

            )

        except ValueError:

            continue



        processing_level = (

            p.get(

                "processingLevel"

            )

        )

        beam_mode = (

            p.get(

                "beamModeType"

            )

        )

        polarization = (

            p.get(

                "polarization"

            )

        )

        flight_direction = (

            p.get(

                "flightDirection"

            )

        )



        if processing_level != "SLC":

            continue

        if beam_mode != "IW":

            continue

        if (

            not polarization

            or "VV" not in polarization

        ):

            continue

        if (

            direction is not None

            and flight_direction != direction

        ):

            continue



        scene_period = None

        for index, (

            start,

            end,

        ) in enumerate(

            periods,

            start=1,

        ):

            if (

                start

                <= date_time

                <= end

            ):

                scene_period = index

                break

        if scene_period is None:

            continue



        relative_orbit = (

            p.get(

                "relativeOrbit"

            )

        )

        if relative_orbit is None:

            relative_orbit = (

                p.get(

                    "pathNumber"

                )

            )



        try:

            geometry = shape(

                product.geometry

            )

        except Exception:

            continue



        scene_name = (

            p.get(

                "sceneName"

            )

        )

        if not scene_name:

            continue



        scenes.append(

            {

                "scene_name": scene_name,

                "date": date_time.date(),

                "date_time": date_time,

                "platform": p.get(

                    "platform"

                ),

                "direction": flight_direction,

                "absolute_orbit": p.get(

                    "orbit"

                ),

                "relative_orbit": (

                    relative_orbit

                ),

                "frame": p.get(

                    "frameNumber"

                ),

                "polarization": polarization,

                "mode": beam_mode,

                "processing_level": (

                    processing_level

                ),

                "group_id": p.get(

                    "groupID"

                ),

                "url": p.get(

                    "url"

                ),

                "period": scene_period,

                "geometry": geometry,

            }

        )

    return scenes




# GEODATAFRAME

def create_geodataframe(

    scenes,

):

    columns = [

        "scene_name",

        "date",

        "date_time",

        "platform",

        "direction",

        "absolute_orbit",

        "relative_orbit",

        "frame",

        "polarization",

        "mode",

        "processing_level",

        "group_id",

        "url",

        "period",

        "individual_coverage_pct",

        "new_coverage_pct",

        "selected",

        "geometry",

    ]

    if not scenes:

        return gpd.GeoDataFrame(

            columns=columns,

            geometry="geometry",

            crs=GEOGRAPHIC_CRS,

        )

    return gpd.GeoDataFrame(

        scenes,

        geometry="geometry",

        crs=GEOGRAPHIC_CRS,

    )




# COVERAGE

def prepare_coverage_geometries(

    scene_gdf,

    aoi_geometry,

    aoi_crs,

):

    aoi_gdf = gpd.GeoDataFrame(

        geometry=[

            aoi_geometry

        ],

        crs=aoi_crs,

    )

    aoi_gdf = (

        aoi_gdf

        .to_crs(

            WORKING_CRS

        )

    )

    aoi = (

        aoi_gdf

        .geometry

        .iloc[0]

    )

    scenes = (

        scene_gdf

        .to_crs(

            WORKING_CRS

        )

        .copy()

    )

    return aoi, scenes


def select_date_coverage(

    date_scenes,

    aoi,

    aoi_area,

):


    if date_scenes.empty:

        return (

            date_scenes.copy(),

            0.0,

        )

    candidates = []

    for index, scene in (

        date_scenes.iterrows()

    ):

        geometry = (

            scene.geometry

        )

        intersection = (

            geometry

            .intersection(

                aoi

            )

        )

        area = (

            intersection.area

        )

        percentage = (

            area

            / aoi_area

            * 100

        )

        candidates.append(

            {

                "index": index,

                "geometry": geometry,

                "aoi_intersection": (

                    intersection

                ),

                "coverage_pct": min(

                    percentage,

                    100.0,

                ),

            }

        )

    current_coverage = None

    selected = []

    results = []

    remaining = candidates.copy()

    for _ in range(

        min(

            MAX_SCENES_PER_DATE,

            len(remaining),

        )

    ):

        best = None

        best_new_coverage = 0.0

        for candidate in remaining:

            intersection = (

                candidate[

                    "aoi_intersection"

                ]

            )

            if current_coverage is None:

                new_coverage = (

                    candidate[

                        "coverage_pct"

                    ]

                )

            else:

                new_area = (

                    intersection

                    .difference(

                        current_coverage

                    )

                    .area

                )

                new_coverage = (

                    new_area

                    / aoi_area

                    * 100

                )

            if (

                new_coverage

                > best_new_coverage

            ):

                best = candidate

                best_new_coverage = (

                    new_coverage

                )

        if best is None:

            break

        if (

            best_new_coverage

            <= 0.000001

        ):

            break

        index = (

            best["index"]

        )

        selected.append(

            index

        )

        results.append(

            {

                "index": index,

                "individual_coverage_pct": (

                    best[

                        "coverage_pct"

                    ]

                ),

                "new_coverage_pct": (

                    best_new_coverage

                ),

            }

        )

        if current_coverage is None:

            current_coverage = (

                best[

                    "aoi_intersection"

                ]

            )

        else:

            current_coverage = (

                current_coverage.union(

                    best[

                        "aoi_intersection"

                    ]

                )

            )

        remaining = [

            candidate

            for candidate in remaining

            if candidate[

                "index"

            ] != index

        ]

        total_coverage_pct = (

            current_coverage.area

            / aoi_area

            * 100

        )

        if (

            total_coverage_pct

            >= TARGET_COVERAGE

        ):

            break

    result = (

        date_scenes

        .copy()

    )

    result[

        "individual_coverage_pct"

    ] = 0.0

    result[

        "new_coverage_pct"

    ] = 0.0

    result[

        "selected"

    ] = False

    for item in results:

        index = item["index"]

        result.loc[

            index,

            "individual_coverage_pct",

        ] = item[

            "individual_coverage_pct"

        ]

        result.loc[

            index,

            "new_coverage_pct",

        ] = item[

            "new_coverage_pct"

        ]

        result.loc[

            index,

            "selected",

        ] = True

    if current_coverage is None:

        final_coverage = 0.0

    else:

        final_coverage = (

            current_coverage.area

            / aoi_area

            * 100

        )

    return (

        result,

        min(

            final_coverage,

            100.0,

        ),

    )




# MAIN SELECTION

def select_scenes(

    scene_gdf,

    aoi_geometry,

    aoi_crs,

):

    if scene_gdf.empty:

        return (

            scene_gdf.copy(),

            {},

        )

    aoi, projected_scenes = (

        prepare_coverage_geometries(

            scene_gdf,

            aoi_geometry,

            aoi_crs,

        )

    )

    aoi_area = aoi.area

    if aoi_area <= 0:

        raise ValueError(

            "The AOI area is invalid."

        )

    results = []

    summary = {}

    groups = scene_gdf.groupby(

        [

            "date",

            "direction",

        ]

    )

    for (

        date,

        direction,

    ), original_group in groups:

        indices = (

            original_group.index

            .tolist()

        )

        projected_group = (

            projected_scenes.loc[

                indices

            ]

            .copy()

        )

        selected_scenes, coverage = (

            select_date_coverage(

                projected_group,

                aoi,

                aoi_area,

            )

        )

        results.append(

            selected_scenes

        )

        scenes_selected = (

            selected_scenes[

                selected_scenes[

                    "selected"

                ]

            ]

        )

        summary[

            (

                date,

                direction,

            )

        ] = {

            "date": date,

            "direction": direction,

            "scenes_found": len(

                selected_scenes

            ),

            "scenes_selected": len(

                scenes_selected

            ),

            "coverage_pct": coverage,

        }

    if not results:

        return (

            scene_gdf.copy(),

            summary,

        )

    result = pd.concat(

        results

    )

    result = (

        gpd.GeoDataFrame(

            result,

            geometry="geometry",

            crs=WORKING_CRS,

        )

        .to_crs(

            GEOGRAPHIC_CRS

        )

    )

    return (

        result,

        summary,

    )




# DATE SUMMARY

def get_date_summary(

    scene_gdf,

):

    if scene_gdf.empty:

        return []

    summary = []

    groups = (

        scene_gdf[

            scene_gdf[

                "selected"

            ]

        ]

        .groupby(

            [

                "date",

                "direction",

            ]

        )

    )

    for (

        date,

        direction,

    ), grupo in groups:

        summary.append(

            {

                "date": date,

                "direction": direction,

                "scenes": len(

                    grupo

                ),

                "coverage_pct": (

                    0.0

                ),

            }

        )

    return summary




# DOWNLOAD TABLE

def write_date_downloads(

    f,

    scene_gdf,

    date,

    direction,

    coverage_pct,

):

    scenes = (

        scene_gdf[

            (

                scene_gdf[

                    "date"

                ]

                == date

            )

            & (

                scene_gdf[

                    "direction"

                ]

                == direction

            )

            & (

                scene_gdf[

                    "selected"

                ]

                == True

            )

        ]

        .sort_values(

            "date_time"

        )

    )

    f.write(

        f"#### {direction}\n\n"

    )

    f.write(

        f"**Coverage: "

        f"{coverage_pct:.2f}%**  \n"

    )

    f.write(

        f"Selected scenes: "

        f"{len(scenes)}\n\n"

    )

    if scenes.empty:

        f.write(

            "No scenes selected "

            "for this direction.\n\n"

        )

        return

    for index, (

        _,

        scene,

    ) in enumerate(

        scenes.iterrows(),

        start=1,

    ):

        scene_name = (

            scene[

                "scene_name"

            ]

        )

        url = (

            scene[

                "url"

            ]

        )

        individual_coverage = (

            scene[

                "individual_coverage_pct"

            ]

        )

        new_coverage = (

            scene[

                "new_coverage_pct"

            ]

        )

        f.write(

            f"{index}. "

            f"`{scene_name}`  \n"

        )

        f.write(

            f"   - Individual coverage: "

            f"{individual_coverage:.2f}%  \n"

        )

        f.write(

            f"   - New coverage added: "

            f"{new_coverage:.2f}%  \n"

        )

        if pd.notna(url):

            f.write(

                f"   - [Download SLC from ASF]"

                f"({url})\n\n"

            )

        else:

            f.write(

                "   - Download URL not available.\n\n"

            )




# SAVE RESULTS

def save_results(

    scene_gdf,

    boundary_path,

    periods,

    summary,

):

    area_name = (

        Path(

            boundary_path

        ).stem

    )

    output_folder = (

        DATA_OUTPUTS

        / area_name

    )

    output_folder.mkdir(

        parents=True,

        exist_ok=True,

    )

    print()

    print(

        "Saving results..."

    )

    print(

        f"Folder: "

        f"{output_folder}"

    )



    scenes_gpkg_path = (

        output_folder

        / "sentinel1_scenes.gpkg"

    )

    scenes_csv_path = (

        output_folder

        / "sentinel1_scenes.csv"

    )

    if not scene_gdf.empty:

        scene_gdf.to_file(

            scenes_gpkg_path,

            layer="s1_scenes",

            driver="GPKG",

        )

        (

            scene_gdf

            .drop(

                columns="geometry"

            )

            .to_csv(

                scenes_csv_path,

                index=False,

            )

        )



    markdown_path = (

        output_folder

        / "SENTINEL1_DOWNLOADS.md"

    )

    with open(

        markdown_path,

        "w",

        encoding="utf-8",

    ) as f:

        f.write(

            "# Sentinel-1 — Coverage-based selection\n\n"

        )

        f.write(

            "Automatic selection of Sentinel-1 scenes "

            "SLC IW to maximize the spatial coverage "

            "of the AOI by date and orbit direction.\n\n"

        )



        f.write(

            "## Selection criteria\n\n"

        )

        f.write(

            "Scenes are analyzed separately for "

            "**ASCENDING** and **DESCENDING**. For each "

            "date, the smallest number of "

            "scenes required to maximize coverage "

            "of the boundary.\n\n"

        )

        f.write(

            "The selection first prioritizes the scene that "

            "provides the greatest coverage and then "

            "adds scenes according to the new area they "

            "contribute to the AOI.\n\n"

        )



        f.write(

            "## Queried periods\n\n"

        )

        for index, (

            start,

            end,

        ) in enumerate(

            periods,

            start=1,

        ):

            f.write(

                f"- Period {index}: "

                f"{start:%Y-%m-%d} → "

                f"{end:%Y-%m-%d}\n"

            )

        f.write("\n")



        f.write(

            "## Product\n\n"

        )

        f.write(

            "- Platform: Sentinel-1\n"

        )

        f.write(

            "- Product: SLC (Single Look Complex)\n"

        )

        f.write(

            "- Mode: IW (Interferometric Wide Swath)\n"

        )

        f.write(

            "- Polarization: VV o VV+VH\n"

        )

        f.write("\n")



        f.write(

            "## Summary by date\n\n"

        )

        dates = sorted(

            {

                date

                for (

                    date,

                    _,

                ) in summary.keys()

            }

        )

        if not dates:

            f.write(

                "No results.\n\n"

            )

        for date in dates:

            f.write(

                f"### {date}\n\n"

            )

            for direction in [

                "ASCENDING",

                "DESCENDING",

            ]:

                info = summary.get(

                    (

                        date,

                        direction,

                    )

                )

                if info is None:

                    continue

                coverage_pct = (

                    info[

                        "coverage_pct"

                    ]

                )

                if (

                    coverage_pct

                    >= TARGET_COVERAGE

                ):

                    status = (

                        "100% covered"

                    )

                else:

                    status = (

                        "Maximum available "

                        "coverage"

                    )

                f.write(

                    f"**{direction}**  \n"

                )

                f.write(

                    f"- Coverage: "

                    f"{coverage_pct:.2f}%  \n"

                )

                f.write(

                    f"- Scenes selected_scenes: "

                    f"{info['scenes_selected']}  \n"

                )

                f.write(

                    f"- Status: **{status}**\n\n"

                )



            f.write(

                "#### Downloads\n\n"

            )

            for direction in [

                "ASCENDING",

                "DESCENDING",

            ]:

                info = summary.get(

                    (

                        date,

                        direction,

                    )

                )

                if info is None:

                    continue

                write_date_downloads(

                    f,

                    scene_gdf,

                    date,

                    direction,

                    info[

                        "coverage_pct"

                    ],

                )



        f.write(

            "## Generated files\n\n"

        )

        f.write(

            "- `sentinel1_scenes.gpkg`: "

            "footprints and metadata of all scenes "

            "found and their selection status.\n"

        )

        f.write(

            "- `sentinel1_escenas.csv`: "

            "metadata of the scenes found.\n"

        )

        f.write(

            "- `SENTINEL1_DOWNLOADS.md`: "

            "coverage summary and download links.\n"

        )

        f.write("\n")



        f.write(

            "## Note about ASCENDING and DESCENDING\n\n"

        )

        f.write(

            "ASCENDING y DESCENDING represent different "

            "radar observation geometries. They are "

            "kept separate to allow selection of "

            "the acquisition that provides the "

            "most suitable spatial coverage for the "

            "area of interest.\n\n"

        )

        f.write(

            "The indicated coverage corresponds to the "

            "spatial coverage of the boundary through the "

            "union of the footprints of the scenes "

            "selected for a given date and orbit direction "

            "determined.\n"

        )



    print()

    print(

        "Generated files:"

    )

    if not scene_gdf.empty:

        print(

            f"  {scenes_gpkg_path}"

        )

        print(

            f"  {scenes_csv_path}"

        )

    print(

        f"  {markdown_path}"

    )




# MAIN

def main():

    args = parse_args()

    periods = parse_periods(

        args.period

    )

    boundary_path = Path(

        args.boundary

    )

    if not boundary_path.exists():

        raise FileNotFoundError(

            f"No existe el archivo: "

            f"{boundary_path}"

        )



    geometry, aoi_crs = (

        load_aoi(

            boundary_path

        )

    )



    temp_gdf = gpd.GeoDataFrame(

        geometry=[

            geometry

        ],

        crs=aoi_crs,

    )

    wgs84_geometry = (

        temp_gdf

        .to_crs(

            GEOGRAPHIC_CRS

        )

        .geometry

        .iloc[0]

    )

    bbox_wkt = (

        build_bbox_wkt(

            wgs84_geometry

        )

    )



    print()

    print(

        "=" * 60

    )

    print(

        "SENTINEL-1 SELECTOR"

    )

    print(

        "=" * 60

    )

    print(

        f"AOI: {boundary_path}"

    )

    print(

        f"BBOX: {bbox_wkt}"

    )

    print()

    print(

        "Periods:"

    )

    for index, (

        start,

        end,

    ) in enumerate(

        periods,

        start=1,

    ):

        print(

            f"  {index}. "

            f"{start:%Y-%m-%d} → "

            f"{end:%Y-%m-%d}"

        )

    print()

    print(

        "Product: Sentinel-1 SLC"

    )

    print(

        "Mode: IW"

    )

    print(

        "Polarization: VV / VV+VH"

    )

    if args.direction:

        print(

            f"Direction: "

            f"{args.direction}"

        )

    else:

        print(

            "Directions: "

            "ASCENDING + DESCENDING"

        )



    scenes = search_scenes(

        bbox_wkt,

        periods,

        args.direction,

    )

    print()

    print(

        f"Valid SLC scenes: "

        f"{len(scenes)}"

    )

    if not scenes:

        print()

        print(

            "No compatible scenes "

            "were found."

        )

        return



    scene_gdf = (

        create_geodataframe(

            scenes

        )

    )



    print()

    print(

        "Selecting scenes by "

        "date and coverage..."

    )

    (

        scene_gdf,

        summary,

    ) = select_scenes(

        scene_gdf,

        geometry,

        aoi_crs,

    )



    print()

    print(

        "=" * 60

    )

    print(

        "RESULTS"

    )

    print(

        "=" * 60

    )

    dates = sorted(

        {

            date

            for (

                date,

                _,

            ) in summary.keys()

        }

    )

    for date in dates:

        print()

        print(

            f"{date}"

        )

        for direction in [

            "ASCENDING",

            "DESCENDING",

        ]:

            info = summary.get(

                (

                    date,

                    direction,

                )

            )

            if info is None:

                continue

            coverage_pct = (

                info[

                    "coverage_pct"

                ]

            )

            scenes_selected = (

                info[

                    "scenes_selected"

                ]

            )

            print(

                f"  {direction}:"

            )

            print(

                f"    Coverage: "

                f"{coverage_pct:.2f}%"

            )

            print(

                f"    Scenes selected_scenes: "

                f"{scenes_selected}"

            )

            direction_scenes = (

                scene_gdf[

                    (

                        scene_gdf[

                            "date"

                        ]

                        == date

                    )

                    & (

                        scene_gdf[

                            "direction"

                        ]

                        == direction

                    )

                    & (

                        scene_gdf[

                            "selected"

                        ]

                        == True

                    )

                ]

            )

            for _, scene in (

                direction_scenes.iterrows()

            ):

                print(

                    f"      - "

                    f"{scene['scene_name']}"

                )



    save_results(

        scene_gdf,

        boundary_path,

        periods,

        summary,

    )



    total_selected = int(

        scene_gdf[

            "selected"

        ].sum()

    )

    print()

    print(

        "=" * 60

    )

    print(

        "FINISHED"

    )

    print(

        "=" * 60

    )

    print(

        f"Scenes found: "

        f"{len(scene_gdf)}"

    )

    print(

        f"Selected scenes: "

        f"{total_selected}"

    )

    print()

    print(

        "Selection was performed "

        "by spatial coverage, "

        "date, and orbit direction."

    )


if __name__ == "__main__":

    main()
