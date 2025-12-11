#!/bin/bash
#
# CPU Stress Injector
# Creates high CPU load to simulate resource exhaustion
#

set -e

# Configuration
CPU_CORES=${CPU_CORES:-2}
DURATION_SECONDS=${DURATION_SECONDS:-300}
CPU_PERCENT=${CPU_PERCENT:-80}

echo "========================================="
echo "CPU Stress Injector"
echo "========================================="
echo "CPU Cores: $CPU_CORES"
echo "Duration: $DURATION_SECONDS seconds"
echo "Target CPU: $CPU_PERCENT%"
echo "========================================="

# Check if stress-ng is available
if ! command -v stress-ng &> /dev/null; then
    echo "ERROR: stress-ng not found. Installing..."
    
    # Try to install stress-ng
    if command -v apt-get &> /dev/null; then
        apt-get update && apt-get install -y stress-ng
    elif command -v yum &> /dev/null; then
        yum install -y stress-ng
    elif command -v apk &> /dev/null; then
        apk add --no-cache stress-ng
    else
        echo "ERROR: Cannot install stress-ng. Package manager not found."
        exit 1
    fi
fi

# Start CPU stress
echo "Starting CPU stress..."
echo "Start time: $(date)"

stress-ng --cpu $CPU_CORES \
          --cpu-load $CPU_PERCENT \
          --timeout ${DURATION_SECONDS}s \
          --metrics-brief \
          --verbose

echo "CPU stress completed"
echo "End time: $(date)"
