import os
import traceback
import processing

from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtCore import QVariant


# =========================================================
# USER INPUTS
# Define the input raster, manually prepared training sample
# layer, output folder, and class field name.
# =========================================================

raster_path = r"C:\Users\Sindhuja.Achutuni\Documents\OBIA\HLS.L30.T14RNU.2020103T170237.v2.0.B_stack_raster.tif"
sample_path = r"C:\Users\Sindhuja.Achutuni\Documents\OBIA\sample.shp"
output_dir = r"C:\Users\Sindhuja.Achutuni\Documents\OBIA\OBIA_Auto_Script"

class_field = "class_id"

# HLS-friendly segmentation parameters
# These values control the Mean Shift segmentation behavior.
spatial_radius = 3
range_radius = 0.05
min_region_size = 50
meanshift_threshold = 0.1
meanshift_maxiter = 100

# Rasterize final output or not
# Rasterize final classification or not.
do_rasterize = True
rasterize_xres = 30
rasterize_yres = 30


# =========================================================
# OUTPUT PATHS
# These are the files the script will create.
# =========================================================

os.makedirs(output_dir, exist_ok=True)

segments_raster = os.path.join(output_dir, "segments_labels.tif")
segments_vector = os.path.join(output_dir, "segments.gpkg")
segments_fixed = os.path.join(output_dir, "segments_fixed.gpkg")
joined_segments = os.path.join(output_dir, "segments_joined.gpkg")
model_file = os.path.join(output_dir, "rf_model.txt")
classified_segments = os.path.join(output_dir, "classified_segments.gpkg")
classified_raster = os.path.join(output_dir, "classified_segments_raster.tif")
dissolved_segments = os.path.join(output_dir, "classified_segments_dissolved.gpkg")
area_output = os.path.join(output_dir, "classified_segments_dissolved_area.gpkg")

# =========================================================
# HELPER FUNCTIONS
# These are small utility functions for logging, validation,
# reading field names, checking class field type, and
# deleting old outputs before rerunning the script.
# =========================================================

def log(msg):
    print(f"[INFO] {msg}")

def check_layer(layer, name):
    if not layer or not layer.isValid():
        raise Exception(f"{name} is not valid.")

def get_field_names(layer):
    return [f.name() for f in layer.fields()]

def ensure_numeric_class_field(layer, field_name):
    idx = layer.fields().indexFromName(field_name)
    if idx == -1:
        raise Exception(f"Field '{field_name}' not found in sample layer.")
    field_type = layer.fields()[idx].type()
    if field_type not in (
        QVariant.Int, QVariant.UInt,
        QVariant.LongLong, QVariant.ULongLong,
        QVariant.Double
    ):
        raise Exception(f"Field '{field_name}' must be numeric.")

def delete_if_exists(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"[WARN] Could not delete {path}: {e}")



# =========================================================
# STEP 0: LOAD INPUTS
# Load raster and manually prepared training samples.
# Check validity and read number of raster bands.
# =========================================================

try:
    log("Loading raster...")
    raster_layer = QgsRasterLayer(raster_path, "input_raster")
    check_layer(raster_layer, "Raster layer")
    QgsProject.instance().addMapLayer(raster_layer)

    log("Loading training points...")
    sample_layer = QgsVectorLayer(sample_path, "training_points", "ogr")
    check_layer(sample_layer, "Training sample layer")
    QgsProject.instance().addMapLayer(sample_layer)

    ensure_numeric_class_field(sample_layer, class_field)

    band_count = raster_layer.bandCount()
    log(f"Raster bands: {band_count}")
    log(f"Training fields: {get_field_names(sample_layer)}")

except Exception:
    print(traceback.format_exc())
    raise


# =========================================================
# STEP 1: OTB SEGMENTATION
# Run OTB Mean Shift segmentation to create image objects.
# Save both raster labels and vector segment polygons.
# =========================================================

try:
    log("STEP 1: Running OTB Segmentation...")

    seg_params = {
        "in": raster_path,
        "filter": "meanshift",
        "filter.meanshift.spatialr": spatial_radius,
        "filter.meanshift.ranger": range_radius,
        "filter.meanshift.minsize": min_region_size,
        "filter.meanshift.thres": meanshift_threshold,
        "filter.meanshift.maxiter": meanshift_maxiter,

        # included to avoid wrapper validation issue
        "filter.cc.expr": "distance < 1",

        "mode": "vector",
        "mode.vector.out": segments_vector,
        "mode.vector.neighbor": False,
        "mode.vector.stitch": True,
        "mode.vector.minsize": 1,
        "mode.vector.simplify": 0.1,
        "mode.vector.layername": "segments",
        "mode.vector.fieldname": "DN",
        "mode.vector.tilesize": 1024,
        "mode.vector.startlabel": 1,

        "mode.raster.out": segments_raster
    }

    seg_result = processing.run("otb:Segmentation", seg_params)
    log(f"Segmentation complete: {seg_result}")

    seg_layer = QgsVectorLayer(segments_vector, "segments_raw", "ogr")
    check_layer(seg_layer, "Segments layer")
    QgsProject.instance().addMapLayer(seg_layer)

except Exception:
    print(traceback.format_exc())
    raise


# =========================================================
# STEP 2: FIX GEOMETRIES
# Clean the segmentation polygons so later tools do not fail.
# =========================================================

try:
    log("STEP 2: Fixing segment geometries...")

    fix_result = processing.run("native:fixgeometries", {
        "INPUT": segments_vector,
        "OUTPUT": segments_fixed
    })

    log(f"Fixed geometry output: {fix_result}")

    fixed_layer = QgsVectorLayer(segments_fixed, "segments_fixed", "ogr")
    check_layer(fixed_layer, "Fixed segments layer")
    QgsProject.instance().addMapLayer(fixed_layer)

except Exception:
    print(traceback.format_exc())
    raise


# =========================================================
# STEP 3: ZONAL STATISTICS
# For each raster band, calculate mean and standard deviation
# for every segment polygon. Save outputs band by band.
# =========================================================

try:
    log("STEP 3: Running zonal statistics...")

    current_input = segments_fixed

    for band in range(1, band_count + 1):
        prefix = f"b{band}_"
        band_output = os.path.join(output_dir, f"segments_zs_band{band}.gpkg")

        delete_if_exists(band_output)

        log(f"Processing zonal stats for band {band}...")

        zs_result = processing.run("native:zonalstatisticsfb", {
            "INPUT": current_input,
            "INPUT_RASTER": raster_path,
            "RASTER_BAND": band,
            "COLUMN_PREFIX": prefix,
            "STATISTICS": [2, 4],   # mean, stddev
            "OUTPUT": band_output
        })

        current_input = zs_result["OUTPUT"]

    segments_stats = current_input

    seg_stats_layer = QgsVectorLayer(segments_stats, "segments_with_stats", "ogr")
    check_layer(seg_stats_layer, "Segments stats layer")
    QgsProject.instance().addMapLayer(seg_stats_layer)

    log(f"Fields after zonal stats: {get_field_names(seg_stats_layer)}")

except Exception:
    print(traceback.format_exc())
    raise


# =========================================================
# STEP 4: JOIN TRAINING POINTS TO SEGMENTS
# Transfer class_id from manual training points to the
# segment polygons using spatial intersection.
# =========================================================

try:
    log("STEP 4: Joining training points to segments...")

    join_result = processing.run("native:joinattributesbylocation", {
        "INPUT": segments_stats,
        "JOIN": sample_path,
        "PREDICATE": [0],   # intersects
        "JOIN_FIELDS": [class_field],
        "METHOD": 1,        # one-to-one
        "DISCARD_NONMATCHING": True,
        "PREFIX": "",
        "OUTPUT": joined_segments
    })

    log(f"Join completed: {join_result}")

    joined_layer = QgsVectorLayer(joined_segments, "joined_segments", "ogr")
    check_layer(joined_layer, "Joined layer")
    QgsProject.instance().addMapLayer(joined_layer)

    joined_fields = get_field_names(joined_layer)
    log(f"Fields after join: {joined_fields}")

    if class_field not in joined_fields:
        raise Exception(f"'{class_field}' not found after join.")

except Exception:
    print(traceback.format_exc())
    raise


# =========================================================
# STEP 5: DEFINE FEATURE FIELDS
# Choose which fields will be used as predictor variables
# for training and classification.
# =========================================================

try:
    log("STEP 5: Defining feature fields...")

    candidate_fields = get_field_names(joined_layer)
    feature_fields = []

    for i in range(1, band_count + 1):
        mean_name = f"b{i}_mean"

        if f"b{i}_stdev" in candidate_fields:
            std_name = f"b{i}_stdev"
        elif f"b{i}_stddev" in candidate_fields:
            std_name = f"b{i}_stddev"
        else:
            raise Exception(f"Missing stdev/stddev field for band {i}")

        if mean_name not in candidate_fields:
            raise Exception(f"Missing mean field for band {i}")

        feature_fields.extend([mean_name, std_name])

    log(f"Using feature fields: {feature_fields}")

except Exception:
    print(traceback.format_exc())
    raise

# =========================================================
# STEP 6: TRAIN RANDOM FOREST CLASSIFIER
# Train the classifier using joined segments, zonal
# statistics features, and class_id as target label.
# =========================================================

try:
    log("STEP 6: Training classifier...")

    train_params = {
        "io.vd": joined_segments,
        "feat": feature_fields,
        "cfield": class_field,
        "classifier": "rf",
        "io.out": model_file
    }

    train_result = processing.run("otb:TrainVectorClassifier", train_params)
    log(f"Training complete: {train_result}")
    log(f"Model saved at: {model_file}")

except Exception:
    print(traceback.format_exc())
    raise


# =========================================================
# STEP 7: CLASSIFY ALL SEGMENTS
# Apply the trained model to all segments and create a
# predicted class field.
# =========================================================

try:
    log("STEP 7: Classifying all segments...")

    classify_params = {
        "in": segments_stats,
        "model": model_file,
        "feat": feature_fields,
        "cfield": "predicted",
        "out": classified_segments
    }

    classify_result = processing.run("otb:VectorClassifier", classify_params)
    log(f"Classification complete: {classify_result}")

    classified_layer = QgsVectorLayer(classified_segments, "classified_segments", "ogr")
    check_layer(classified_layer, "Classified segments")
    QgsProject.instance().addMapLayer(classified_layer)

    log(f"Final classified fields: {get_field_names(classified_layer)}")

except Exception:
    print(traceback.format_exc())
    raise


# =========================================================
# STEP 8: OPTIONAL RASTERIZATION
# Convert classified polygons to a raster using predicted
# values if raster output is needed.
# =========================================================

if do_rasterize:
    try:
        log("STEP 8: Rasterizing classified polygons...")

        ext = raster_layer.extent()
        extent_str = f"{ext.xMinimum()},{ext.xMaximum()},{ext.yMinimum()},{ext.yMaximum()}"

        rast_result = processing.run("gdal:rasterize", {
            "INPUT": classified_segments,
            "FIELD": "predicted",
            "BURN": 0,
            "USE_Z": False,
            "UNITS": 1,
            "WIDTH": rasterize_xres,
            "HEIGHT": rasterize_yres,
            "EXTENT": extent_str,
            "NODATA": 0,
            "DATA_TYPE": 3,
            "INIT": None,
            "INVERT": False,
            "EXTRA": "",
            "OUTPUT": classified_raster
        })

        log(f"Rasterization complete: {rast_result}")

        class_raster_layer = QgsRasterLayer(classified_raster, "classified_raster")
        check_layer(class_raster_layer, "Classified raster")
        QgsProject.instance().addMapLayer(class_raster_layer)

    except Exception:
        print(traceback.format_exc())
        raise

# =========================================================
# STEP 9: OPTIONAL DISSOLVE BY CLASS
# Merge polygons that belong to the same predicted class.
# =========================================================

try:
    log("STEP 9: Dissolving classified polygons by class...")

    dissolve_result = processing.run("native:dissolve", {
        "INPUT": classified_segments,
        "FIELD": ["predicted"],
        "SEPARATE_DISJOINT": False,
        "OUTPUT": dissolved_segments
    })

    log(f"Dissolve complete: {dissolve_result}")

    dissolved_layer = QgsVectorLayer(dissolved_segments, "classified_dissolved", "ogr")
    check_layer(dissolved_layer, "Dissolved classified layer")
    QgsProject.instance().addMapLayer(dissolved_layer)

except Exception:
    print(traceback.format_exc())
    raise


# ========================
# STEP 10: OPTIONAL AREA CALCULATION
# Add an area field to the dissolved polygons.
# =========================================================

try:
    log("STEP 10: Calculating area field...")

    area_result = processing.run("native:fieldcalculator", {
        "INPUT": dissolved_segments,
        "FIELD_NAME": "area",
        "FIELD_TYPE": 0,
        "FIELD_LENGTH": 20,
        "FIELD_PRECISION": 4,
        "FORMULA": "$area",
        "OUTPUT": area_output
    })

    log(f"Area calculation complete: {area_result}")

    area_layer = QgsVectorLayer(area_output, "classified_dissolved_area", "ogr")
    check_layer(area_layer, "Area layer")
    QgsProject.instance().addMapLayer(area_layer)

except Exception:
    print(traceback.format_exc())
    raise
    


# =========================================================
# DONE
# Print the locations of all important output files.
# =========================================================

log("OBIA workflow completed successfully.")
log(f"Raw segments: {segments_vector}")
log(f"Fixed segments: {segments_fixed}")
log(f"Joined segments: {joined_segments}")
log(f"Model file: {model_file}")
log(f"Classified segments: {classified_segments}")
log(f"Dissolved segments: {dissolved_segments}")
log(f"Area output: {area_output}")
if do_rasterize:
    log(f"Classified raster: {classified_raster}")