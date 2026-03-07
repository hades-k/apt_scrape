#!/usr/bin/env zsh

# Configuration
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
CLI_SCRIPT="cli.py"
OUTPUT_DIR="results/latest/batch"

# Search parameters
CITY="milano"
OPERATION="affitto"
PROPERTY_TYPES="appartamenti,attici"
MAX_PRICE=1200
MIN_SQM=55
MIN_ROOMS=2
SORT="piu-recenti"
SOURCE="immobiliare"
START_PAGE=1
END_PAGE=5

# List of areas to scrape (add or remove as needed)
AREAS=(
  "bicocca"
  "niguarda"
  "precotto"
  "loreto"
  "città-studi"
  "lambrate"
  "turro"
  "greco"
  "crescenzago"
  "centrale"
)

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Log file
LOG_FILE="${OUTPUT_DIR}/scrape_log_$(date +%Y%m%d_%H%M%S).txt"

echo "=== Starting multi-area scrape at $(date) ===" | tee "$LOG_FILE"
echo "City: $CITY" | tee -a "$LOG_FILE"
echo "Property types: $PROPERTY_TYPES" | tee -a "$LOG_FILE"
echo "Price: max ${MAX_PRICE}, Size: min ${MIN_SQM}m², Rooms: min ${MIN_ROOMS}" | tee -a "$LOG_FILE"
echo "Pages: ${START_PAGE}-${END_PAGE}" | tee -a "$LOG_FILE"
echo "Areas to scrape: ${#AREAS[@]}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Counter for success/failure
SUCCESS_COUNT=0
FAIL_COUNT=0

# Loop through each area
for AREA in "${AREAS[@]}"; do
  echo "----------------------------------------" | tee -a "$LOG_FILE"
  echo "[$(date +%H:%M:%S)] Scraping area: $AREA" | tee -a "$LOG_FILE"
  
  # Generate output filename
  OUTPUT_FILE="${OUTPUT_DIR}/${CITY}_${AREA}_${PROPERTY_TYPES//,/_}_pages${START_PAGE}_${END_PAGE}_recent.json"
  
  # Run the scraper
  "$PYTHON_BIN" "$CLI_SCRIPT" search \
    --city "$CITY" \
    --area "$AREA" \
    --operation "$OPERATION" \
    --property-type "$PROPERTY_TYPES" \
    --max-price "$MAX_PRICE" \
    --min-sqm "$MIN_SQM" \
    --min-rooms "$MIN_ROOMS" \
    --sort "$SORT" \
    --source "$SOURCE" \
    --start-page "$START_PAGE" \
    --end-page "$END_PAGE" \
    -o "$OUTPUT_FILE" 2>&1 | tee -a "$LOG_FILE"
  
  # Check exit status (zsh: pipestatus is lowercase and 1-indexed)
  if [ ${pipestatus[1]} -eq 0 ]; then
    echo "✓ Success: $AREA → $OUTPUT_FILE" | tee -a "$LOG_FILE"
    ((SUCCESS_COUNT++))
  else
    echo "✗ Failed: $AREA" | tee -a "$LOG_FILE"
    ((FAIL_COUNT++))
  fi
  
  echo "" | tee -a "$LOG_FILE"
  
  # Optional: Add a delay between scrapes to be respectful
  # sleep 5
done

echo "========================================" | tee -a "$LOG_FILE"
echo "=== Scraping completed at $(date) ===" | tee -a "$LOG_FILE"
echo "Success: $SUCCESS_COUNT" | tee -a "$LOG_FILE"
echo "Failed: $FAIL_COUNT" | tee -a "$LOG_FILE"
echo "Log saved to: $LOG_FILE" | tee -a "$LOG_FILE"
