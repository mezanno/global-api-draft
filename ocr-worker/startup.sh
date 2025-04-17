#!/bin/bash

# Startup script for the worker
# Ensures assets are downloaded, or downloads them if not
# Then starts the worker using provided command

# stop on errors
set -e
# stop on unset variables
set -u
# stop on pipe failures
set -o pipefail
# stop on errors in command substitutions
set -o posix


# Capture all parameters as the final command to be run
COMMAND="$@"

# List of files, expected sha256 hashes (sha256sum), and their respective URLs
declare -A files
files=(
    # PERO pero_eu_cz_print_newspapers_2022-09-26
    ["config_cpu.ini"]="c385bf7032832d1ca1dd55465fc22dc6892c4f02e04a395abe12dd0a2c094a84"
    ["OCR_350000.pt.cpu"]="0ae48c6577a99cc1482aa90b3030d6e827b333e267c52e32e999bd7010d7f432"
    ["ocr_engine.json"]="3cea9b6a9ed754d8549f1d02cb8d64558d90cfc301b69b001d10a5d13b4713a6"
    ["ParseNet_296000.pt.cpu"]="38ce221ecdb97eab4b48f54c4732172a9b8bee5264b1c89e336a52bab7384765"

    # PERO pero-printed_modern-public-2022-11-18
    # ["config_cpu.ini"]="c385bf7032832d1ca1dd55465fc22dc6892c4f02e04a395abe12dd0a2c094a84"
    # ["ocr_engine.json"]="e26704f506e9c33a914fda814f418e1f6a79381cc4cbff8dd327daa7dde16c94"
    # ["ParseNet_296000.pt.cpu"]="38ce221ecdb97eab4b48f54c4732172a9b8bee5264b1c89e336a52bab7384765"
    # ["VGG_LSTM_B64_L17_S4_CB4.2022-09-22.700000.pt.cpu"]="0af7afcf23ab7cbf082fbcc3c6a93dbe7f5641c3fbc744d3b26d31796548ff23"

    # PERO pero_eu_cz_print_newspapers_2020-10-07
    # ["ParseNet.pb"]="5714e1898b99d8048dcc9ae272594869f531773fe91d1a44104dbb7c6b5824f2"
    # ["checkpoint_350000.pth"]="d134a7ad71615019def208900816ac35eebf8af1c70b343f223a9a34fecf5086"
    # ["config.ini"]="b72528325817ead2427f24ac2348f1f37e436fab2a732ca717ef3f620e6cce3d"
    # ["ocr_engine.json"]="ec8724d1622a1f08d32acba8a4cd6064e966bb57f631f7d4ca1558e7fe67d135"
    # TORCH-HUB
    # ["vgg16-397923af.pth"]="397923af8e79cdbb6a7127f12361acd7a2f83e06b05044ddf496e83de57a5bf0"
)

PERO_CONFIG_DIR="/data/pero_ocr/pero_eu_cz_print_newspapers_2022-09-26"
PERO_DOWNLOAD_BASE_URL="https://www.lrde.epita.fr/~jchazalo/SHARE/pero_eu_cz_print_newspapers_2022-09-26"


declare -A destinations
destinations=(
    # PERO pero_eu_cz_print_newspapers_2022-09-26
    ["config_cpu.ini"]="${PERO_CONFIG_DIR}/config_cpu.ini"
    ["OCR_350000.pt.cpu"]="${PERO_CONFIG_DIR}/OCR_350000.pt.cpu"
    ["ocr_engine.json"]="${PERO_CONFIG_DIR}/ocr_engine.json"
    ["ParseNet_296000.pt.cpu"]="${PERO_CONFIG_DIR}/ParseNet_296000.pt.cpu"

    # ["config_cpu.ini"]="${PERO_CONFIG_DIR}/config_cpu.ini"
    # ["ocr_engine.json"]="${PERO_CONFIG_DIR}/ocr_engine.json"
    # ["ParseNet_296000.pt.cpu"]="${PERO_CONFIG_DIR}/ParseNet_296000.pt.cpu"
    # ["VGG_LSTM_B64_L17_S4_CB4.2022-09-22.700000.pt.cpu"]="${PERO_CONFIG_DIR}/VGG_LSTM_B64_L17_S4_CB4.2022-09-22.700000.pt.cpu"

    # ["ParseNet.pb"]="${PERO_CONFIG_DIR}/ParseNet.pb"
    # ["checkpoint_350000.pth"]="${PERO_CONFIG_DIR}/checkpoint_350000.pth"
    # ["config.ini"]="${PERO_CONFIG_DIR}/config.ini"
    # ["ocr_engine.json"]="${PERO_CONFIG_DIR}/ocr_engine.json"
    # ["vgg16-397923af.pth"]="/root/.cache/torch/hub/checkpoints/vgg16-397923af.pth"
)
declare -A urls
urls=(
    # PERO pero_eu_cz_print_newspapers_2022-09-26
    ["config_cpu.ini"]="${PERO_DOWNLOAD_BASE_URL}/config_cpu.ini"
    ["OCR_350000.pt.cpu"]="${PERO_DOWNLOAD_BASE_URL}/OCR_350000.pt.cpu"
    ["ocr_engine.json"]="${PERO_DOWNLOAD_BASE_URL}/ocr_engine.json"
    ["ParseNet_296000.pt.cpu"]="${PERO_DOWNLOAD_BASE_URL}/ParseNet_296000.pt.cpu"

    # ["config_cpu.ini"]="${PERO_DOWNLOAD_BASE_URL}/config_cpu.ini"
    # ["ocr_engine.json"]="${PERO_DOWNLOAD_BASE_URL}/ocr_engine.json"
    # ["ParseNet_296000.pt.cpu"]="${PERO_DOWNLOAD_BASE_URL}/ParseNet_296000.pt.cpu"
    # ["VGG_LSTM_B64_L17_S4_CB4.2022-09-22.700000.pt.cpu"]="${PERO_DOWNLOAD_BASE_URL}/VGG_LSTM_B64_L17_S4_CB4.2022-09-22.700000.pt.cpu"

    # ["ParseNet.pb"]="${PERO_DOWNLOAD_BASE_URL}/ParseNet.pb"
    # ["checkpoint_350000.pth"]="${PERO_DOWNLOAD_BASE_URL}/checkpoint_350000.pth"
    # ["config.ini"]="${PERO_DOWNLOAD_BASE_URL}/config.ini"
    # ["ocr_engine.json"]="${PERO_DOWNLOAD_BASE_URL}/ocr_engine.json"
    # ["vgg16-397923af.pth"]="https://www.lrde.epita.fr/~jchazalo/SHARE/vgg16-397923af.pth"
    # ["vgg16-397923af.pth"]="https://download.pytorch.org/models/vgg16-397923af.pth"
)

# Function to check if a file exists and matches the expected hash
check_file() {
    local file=$1
    local expected_hash=$2
    if [[ -f "$file" ]]; then
        # Calculate the hash of the file
        local hash=$(sha256sum "$file" | awk '{print $1}')
        if [[ "$hash" == "$expected_hash" ]]; then
            echo "File $file is present and matches the expected hash."
            return 0
        else
            echo "File $file is present but does not match the expected hash."
            return 1
        fi
    else
        echo "File $file is missing."
        return 1
    fi
}
# Function to download the file
download_file() {
    local file=$1
    local url=$2
    echo "Downloading $file..."
    curl --silent --fail --show-error --output "$file" "$url"
    if [[ $? -ne 0 ]]; then
        echo "Failed to download $file."
        return 1
    fi
    return 0
}
# Function to download all files
download_all_files() {
    for file in "${!files[@]}"; do
        local expected_hash=${files[$file]}
        local file_path=${destinations[$file]}
        local dir_path=$(dirname "$file_path")
        # Create the directory if it doesn't exist
        if [[ ! -d "$dir_path" ]]; then
            echo "Creating directory $dir_path."
            mkdir -p "$dir_path"
        fi
        # Check if the file exists and matches the expected hash
        # If not, download it
        local url=${urls[$file]}
        if ! check_file "$file_path" "$expected_hash"; then
            download_file "$file_path" "$url"
            if [[ $? -ne 0 ]]; then
                echo "Failed to download $file. Exiting."
                exit 1
            fi
            # Verify the downloaded file
            echo "Verifying downloaded file $file_path..."
            if ! check_file "$file_path" "$expected_hash"; then
                echo "Downloaded file $file_path does not match the expected hash."
                echo "Expected: $expected_hash"
                echo "Actual: $(sha256sum "$file_path" | awk '{print $1}')"
                echo "Removing file and exiting."
                rm "$file_path"
                exit 1
            fi
        fi
    done
}
# Main script
echo "Downloading files if necessary..."
download_all_files


# Start the worker
echo "Running command: $COMMAND"
exec $COMMAND
