#!/bin/sh
# AdvancedBootLogoSwapper Plugin Installer
# Version: 1.0.0
# Author: MNASR

echo "Starting installation..."

sleep 3

if [ -d /usr/lib/enigma2/python/Plugins/Extensions/AdvancedBootLogoSwapper ]; then
    echo "> Removing previous installation..."
    rm -rf /usr/lib/enigma2/python/Plugins/Extensions/AdvancedBootLogoSwapper
fi

status_file='/var/lib/opkg/status'
package_name='enigma2-plugin-extensions-advancedbootlogoswapper'

if [ -f "$status_file" ] && grep -q "$package_name" "$status_file"; then
    echo "> Removing old opkg package..."
    opkg remove "$package_name"
fi

sleep 2

echo "> Downloading AdvancedBootLogoSwapper..."
wget -q -O /tmp/AdvancedBootLogoSwapper.tar.gz "https://github.com/popking159/abls/raw/refs/heads/main/AdvancedBootLogoSwapper.tar.gz"

if [ $? -ne 0 ]; then
    echo "ERROR: Download failed!"
    exit 1
fi

echo "> Installing..."
tar -xzf /tmp/AdvancedBootLogoSwapper.tar.gz -C /
if [ $? -ne 0 ]; then
    echo "ERROR: Extraction failed!"
    exit 1
fi

rm -f /tmp/AdvancedBootLogoSwapper.tar.gz
sleep 2

sync
echo "========================================================="
echo "===                      FINISHED                     ==="
echo "===                       MNASR                       ==="
echo "========================================================="
echo "     AdvancedBootLogoSwapper installed successfully!     "
echo "========================================================="

exit 0
