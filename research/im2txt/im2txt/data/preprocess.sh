#!/bin/bash


# usage:
#  ./preprocess.sh [OUTPUT_DIR]
set -e


if [ -z "$1" ]; then
  echo "usage preproces.sh [data dir]"
  exit
fi

if [ "$(uname)" == "Darwin" ]; then
  UNZIP="tar -xf"
else
  UNZIP="unzip -nq"
fi

# Create the output directories.
OUTPUT_DIR="out/${1%/}"
SCRATCH_DIR="${OUTPUT_DIR}/raw-data"
mkdir -p "${OUTPUT_DIR}"
mkdir -p "${SCRATCH_DIR}"
CURRENT_DIR=$(pwd)
WORK_DIR="$0.runfiles/im2txt/im2txt"


# Helper function to download and unpack a .zip file.
function download_and_unzip() {
  local BASE_URL=${1}
  local FILENAME=${2}
  local UNZIPPED_TEST=${3}

  if [ ! -f ${FILENAME} ]; then
    echo "Downloading ${FILENAME} to $(pwd)"
    wget -nd -c "${BASE_URL}/${FILENAME}"
  else
    echo "Skipping download of ${FILENAME}"
  fi
  if [ ! -d ${UNZIPPED_TEST} ]; then
    echo "Unzipping ${FILENAME}"
    ${UNZIP} ${FILENAME}
  else
    echo "Skipping unzip of ${FILENAME}"
  fi
}

cd ${SCRATCH_DIR}

# Todo Copy CraigsImgs to scratch
TRAIN_IMAGE_DIR="$craigscapImg"
# Todo Copy CraigsCaps to scratch
TRAIN_CAPTIONS_DIR="$craigcapAnno"


# Download the base images.
BASE_IMAGE_URL="http://msvocds.blob.core.windows.net/coco2014"

VAL_IMAGE_FILE="val2014.zip"
VAL_IMAGE_UNZIPPED_TEST="val2014"
download_and_unzip ${BASE_IMAGE_URL} ${VAL_IMAGE_FILE} ${VAL_IMAGE_UNZIPPED_TEST}
VAL_IMAGE_DIR="${SCRATCH_DIR}/val2014"


# Download the base captions.
BASE_CAPTIONS_URL="http://msvocds.blob.core.windows.net/annotations-1-0-3"
CAPTIONS_FILE="captions_train-val2014.zip"
CAPTIONS_FILE_UNZIPPED_TEST="annotations"
download_and_unzip ${BASE_CAPTIONS_URL} ${CAPTIONS_FILE} ${CAPTIONS_FILE_UNZIPPED_TEST}
VAL_CAPTIONS_FILE="${SCRATCH_DIR}/annotations/captions_val2014.json"

# Build TFRecords of the image data.
cd "${CURRENT_DIR}"
BUILD_SCRIPT="./build_mscoco_data.py"


echo "${BUILD_SCRIPT}" \
  --train_image_dir="${TRAIN_IMAGE_DIR}" \
  --val_image_dir="${VAL_IMAGE_DIR}" \
  --train_captions_dir="${TRAIN_CAPTIONS_DIR}" \
  --val_captions_file="${VAL_CAPTIONS_FILE}" \
  --output_dir="${OUTPUT_DIR}" \
  --word_counts_output_file="${OUTPUT_DIR}/word_counts.txt" \
