# OBIA
QGIS OBIA automation script for satellite image segmentation, Random Forest classification, raster output, and area calculation.
# QGIS OBIA Random Forest Classification

This project contains a QGIS Python script for automating Object-Based Image Analysis (OBIA) on satellite imagery. The script uses Orfeo Toolbox (OTB) Mean Shift segmentation, zonal statistics, and Random Forest classification to classify image segments based on training samples.

## Project Overview

The script automates the full OBIA workflow in QGIS, including:

* Loading a satellite raster image
* Loading manually prepared training samples
* Running OTB Mean Shift segmentation
* Fixing segment geometries
* Calculating zonal statistics for each raster band
* Joining training sample class IDs to image segments
* Training a Random Forest classifier
* Classifying all image segments
* Rasterizing the classified output
* Dissolving classified polygons by class
* Calculating area for each classified region

## Tools and Software Required

* QGIS
* Orfeo Toolbox (OTB)
* GDAL
* Python inside QGIS
* Training sample layer with a numeric class field

## Input Files Required

Before running the script, prepare the following inputs:

1. **Stacked satellite raster**

   * Example: HLS or Landsat stacked raster image
   * File type: `.tif`

2. **Training sample layer**

   * Example: manually created training points or polygons
   * File type: `.shp` or `.gpkg`
   * Must include a numeric class field such as `class_id`

3. **Output folder**

   * Folder where all generated results will be saved

## Main Workflow

### 1. Load Inputs

The script loads the raster image and training sample layer into QGIS.

### 2. Run Segmentation

OTB Mean Shift segmentation is used to divide the raster image into meaningful image objects or segments.

### 3. Fix Geometries

The generated segment polygons are cleaned using the QGIS Fix Geometries tool.

### 4. Calculate Zonal Statistics

For each raster band, the script calculates mean and standard deviation values for every segment polygon.

### 5. Join Training Samples

The training sample class values are joined to the segment polygons using spatial intersection.

### 6. Train Random Forest Classifier

A Random Forest model is trained using the zonal statistics fields as input features and the class field as the target label.

### 7. Classify Segments

The trained model is applied to all image segments to generate predicted class values.

### 8. Rasterize Output

The classified vector segments are optionally converted into a classified raster output.

### 9. Dissolve by Class

Segments with the same predicted class are dissolved into larger class-based polygons.

### 10. Calculate Area

An area field is added to the dissolved output to calculate the area of each classified class region.

## Output Files

The script generates the following main outputs:

* `segments_labels.tif`
* `segments.gpkg`
* `segments_fixed.gpkg`
* `segments_joined.gpkg`
* `rf_model.txt`
* `classified_segments.gpkg`
* `classified_segments_raster.tif`
* `classified_segments_dissolved.gpkg`
* `classified_segments_dissolved_area.gpkg`

## How to Run

1. Open QGIS.
2. Make sure Orfeo Toolbox is installed and enabled.
3. Open the QGIS Python Console.
4. Load or paste the script into the editor.
5. Update the input paths in the script:

   * `raster_path`
   * `sample_path`
   * `output_dir`
   * `class_field`
6. Run the script.
7. Check the output folder for generated files.

## Notes

* The training sample layer must contain a numeric class field.
* The raster should be a stacked multi-band raster.
* If individual bands are separate, create a stacked raster first before running the script.
* Segmentation parameters may need to be adjusted depending on image resolution and study area.
* Output quality depends on the accuracy and distribution of training samples.

## Purpose

This project is useful for automating satellite image classification using an OBIA approach in QGIS. It helps reduce manual processing time and creates repeatable outputs for remote sensing and land cover classification projects.
