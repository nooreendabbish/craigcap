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
  local EXT=${3}

  if [ ! -f ${FILENAME}.${EXT} ]; then
    echo "Downloading ${FILENAME}.${EXT} to $(pwd)"
    wget -nd -c "${BASE_URL}/${FILENAME}.${EXT}"
  else
    echo "Skipping download of ${FILENAME}.${EXT}"
  fi
  if [ ! -d ${FILENAME} ]; then
    echo "Unzipping ${FILENAME}.${EXT}"
    ${UNZIP} ${FILENAME}.${EXT}
  else
    echo "skipping unzip of ${FILENAME}.${EXT}"
  fi
}

cd ${SCRATCH_DIR}

# Todo Copy CraigsImgs to scratch
TRAIN_IMAGE_DIR="${SCRATCH_DIR}/trainCraigscap"
# Todo Copy CraigsCaps to scratch
TRAIN_CAPTIONS_FILE="${SCRATCH_DIR}/annotations/captions_trainCraigscap.csv"


# Download the images.
BASE_IMAGE_URL="http://msvocds.blob.core.windows.net/coco2014"

VAL_IMAGE_FILE="val2014"
VAL_IMAGE_FILE_EXT="zip"
download_and_unzip ${BASE_IMAGE_URL} ${VAL_IMAGE_FILE} ${VAL_IMAGE_FILE_EXT}
VAL_IMAGE_DIR="${SCRATCH_DIR}/val2014"

exit

# Download the captions.
#BASE_CAPTIONS_URL="http://msvocds.blob.core.windows.net/annotations-1-0-3"
#CAPTIONS_FILE="captions_train-val2014.zip"
#download_and_unzip ${BASE_CAPTIONS_URL} ${CAPTIONS_FILE}


VAL_CAPTIONS_FILE="${SCRATCH_DIR}/annotations/captions_val2014.json"

# Build TFRecords of the image data.
cd "${CURRENT_DIR}"
BUILD_SCRIPT="${WORK_DIR}/build_mscoco_data"


"${BUILD_SCRIPT}" \
  --train_image_dir="${TRAIN_IMAGE_DIR}" \
  --val_image_dir="${VAL_IMAGE_DIR}" \
  --train_captions_file="${TRAIN_CAPTIONS_FILE}" \
  --val_captions_file="${VAL_CAPTIONS_FILE}" \
  --output_dir="${OUTPUT_DIR}" \
  --word_counts_output_file="${OUTPUT_DIR}/word_counts.txt" \
