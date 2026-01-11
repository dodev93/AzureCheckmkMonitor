#!/bin/bash
#
# Load Test Script
# Makes 1000 parallel HTTP requests using 10 threads
#
# Usage: ./load_test.sh [URL] [THREADS] [REQUESTS]
#   URL: The URL to test (default: http://localhost:8080)
#   THREADS: Number of parallel threads (default: 10)
#   REQUESTS: Total number of requests (default: 1000)
#

set -euo pipefail

# Default values
DEFAULT_URL="${1:-http://localhost:8080}"
THREADS="${2:-10}"
REQUESTS="${3:-1000}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Load Test Configuration"
echo "=========================================="
echo "URL:      $DEFAULT_URL"
echo "Threads:  $THREADS"
echo "Requests: $REQUESTS"
echo "=========================================="
echo ""

# Check if curl is available
if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is not installed${NC}"
    exit 1
fi

# Function to make a single request
make_request() {
    local url="$1"
    local request_num="$2"
    
    # Make the request and capture response
    # -s: silent, -w: write-out format, -o: output to file
    local http_code=$(curl -s -w "%{http_code}" -o /dev/null "$url" 2>/dev/null)
    local exit_code=$?
    
    # if [ $exit_code -eq 0 ] && [ -n "$http_code" ]; then
    #     echo "Request #${request_num}: HTTP ${http_code}"
    #     echo "${request_num},${http_code},SUCCESS" >> /tmp/load_test_results_$$.csv
    # else
    #     echo "Request #${request_num}: FAILED"
    #     echo "${request_num},FAILED,ERROR" >> /tmp/load_test_results_$$.csv
    # fi
}

# Export function so it can be used by xargs
export -f make_request
export DEFAULT_URL

# Initialize results file
echo "request_num,http_code,status" > /tmp/load_test_results_$$.csv

echo -e "${YELLOW}Starting load test...${NC}"
echo ""

# Generate sequence of numbers and pipe to xargs for parallel execution
start_time=$(date +%s)

seq 1 "$REQUESTS" | xargs -n 1 -P "$THREADS" -I {} bash -c 'make_request "$DEFAULT_URL" {}'

end_time=$(date +%s)
total_duration=$((end_time - start_time))

echo ""
echo "=========================================="
echo "Load Test Results"
echo "=========================================="

# Calculate statistics
if [ -f /tmp/load_test_results_$$.csv ]; then
    total_requests=$(tail -n +2 /tmp/load_test_results_$$.csv | wc -l)
    successful=$(tail -n +2 /tmp/load_test_results_$$.csv | grep -v "FAILED" | wc -l)
    failed=$(tail -n +2 /tmp/load_test_results_$$.csv | grep "FAILED" | wc -l)
    
    echo "Total Duration:    ${total_duration}s"
    echo "Total Requests:    $total_requests"
    echo "Successful:        $successful"
    echo "Failed:            $failed"
    if [ "$total_duration" -gt 0 ]; then
        requests_per_sec=$((total_requests / total_duration))
        echo "Requests/sec:      ${requests_per_sec}"
    fi
    
    # Show HTTP status code distribution
    echo ""
    echo "HTTP Status Code Distribution:"
    tail -n +2 /tmp/load_test_results_$$.csv | grep -v "FAILED" | cut -d',' -f2 | sort | uniq -c | sort -rn | while read count code; do
        echo "  ${code}: ${count}"
    done
    
    # Cleanup
    rm -f /tmp/load_test_results_$$.csv
else
    echo -e "${RED}Error: Results file not found${NC}"
fi

echo "=========================================="

# Exit with error if all requests failed
if [ "$failed" -eq "$total_requests" ]; then
    echo -e "${RED}All requests failed!${NC}"
    exit 1
elif [ "$failed" -gt 0 ]; then
    echo -e "${YELLOW}Some requests failed${NC}"
    exit 0
else
    echo -e "${GREEN}All requests completed successfully!${NC}"
    exit 0
fi

