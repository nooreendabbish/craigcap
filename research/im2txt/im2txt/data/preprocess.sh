#!/bin/bash


# usage:
#  ./preprocess.sh
set -e


echo -e "\n\n\tpreprocess.sh - start\n\n"

if [ "$(uname)" == "Darwin" ]; then
  UNZIP="tar -xf"
else
  UNZIP="unzip -nq"
fi

# Create the output directories.
OUTPUT_DIR="dl"
SCRATCH_DIR="${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}"
mkdir -p "${SCRATCH_DIR}"
CURRENT_DIR=$(pwd)


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
TRAIN_IMAGE_DIR="craigscapImg"
# Todo Copy CraigsCaps to scratch
TRAIN_CAPTIONS_DIR="craigcapAnno"


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

echo -e "\n\n\tpreprocess.sh - end\n\n"

echo -e "\n\n\tstarting genTFRecord.py\n\n"

python3 genTFRecord.py \
  \
  --coco_image_dir="${VAL_IMAGE_DIR}" \
  --coco_captions_file="${VAL_CAPTIONS_FILE}" \
  \
  --craigcap_image_dir="${TRAIN_IMAGE_DIR}" \
  --craigcap_captions_dir="${TRAIN_CAPTIONS_DIR}" \
  \
  --output_dir="out" \
  --word_counts_output_file="out/word_counts.txt" \


