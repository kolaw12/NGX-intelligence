#!/bin/bash
# News Fetch Automation Wrapper
# Convenient CLI interface for automated news fetching

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON_SCRIPT="$SCRIPT_DIR/automate_news_fetch.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

show_usage() {
    cat << EOF
${BLUE}News Fetch Automation Wrapper${NC}

${GREEN}Usage:${NC}
    $(basename "$0") [COMMAND] [OPTIONS]

${GREEN}Commands:${NC}
    run                 Run all fetchers (default)
    ngx                 Run NGX Announcements only
    businessday         Run BusinessDay only
    sentiment           Run sentiment analysis only
    test                Quick test run (5 articles max)
    parallel            Run with parallel execution
    help                Show this help message
    logs                Show latest log

${GREEN}Options:${NC}
    --max-articles N    Set max articles per source (default: 100)
    --skip-sentiment    Skip sentiment analysis
    --verbose           Enable verbose logging
    --parallel          Use parallel execution
    --no-sentiment      Alias for --skip-sentiment

${GREEN}Examples:${NC}
    # Run all with default settings
    $(basename "$0") run

    # NGX only with 50 articles max
    $(basename "$0") ngx --max-articles 50

    # BusinessDay with parallel execution
    $(basename "$0") businessday --parallel

    # Quick test (10 articles)
    $(basename "$0") test

    # View recent logs
    $(basename "$0") logs

${GREEN}Scheduled Runs (Nigeria Time):${NC}
    - 8:55 AM (Market Open)
    - 1:00 PM (Mid-Trading)
    - 4:30 PM (After Close)

${YELLOW}Note:${NC} For detailed documentation, see scripts/NEWS_FETCH_AUTOMATION.md

EOF
}

show_logs() {
    LOG_FILE="$PROJECT_ROOT/data/logs/news_fetch_automation.log"
    if [ -f "$LOG_FILE" ]; then
        print_header "Recent Logs (Last 30 lines)"
        tail -30 "$LOG_FILE"
    else
        print_warning "No log file found at $LOG_FILE"
    fi
}

show_metrics() {
    METRICS_FILE="$PROJECT_ROOT/data/logs/news_fetch_metrics.json"
    if [ -f "$METRICS_FILE" ]; then
        print_header "Latest Metrics"
        if command -v jq &> /dev/null; then
            jq '.' "$METRICS_FILE"
        else
            cat "$METRICS_FILE"
        fi
    else
        print_warning "No metrics file found at $METRICS_FILE"
    fi
}

run_fetch() {
    local cmd="python $PYTHON_SCRIPT"
    
    # Parse options
    local args=()
    while [[ $# -gt 0 ]]; do
        case $1 in
            --max-articles)
                args+=("$1" "$2")
                shift 2
                ;;
            --skip-sentiment|--no-sentiment)
                args+=("--skip-sentiment")
                shift
                ;;
            --verbose)
                args+=("--verbose")
                shift
                ;;
            --parallel)
                args+=("--parallel")
                shift
                ;;
            *)
                shift
                ;;
        esac
    done
    
    print_header "Starting News Fetch Automation"
    cd "$PROJECT_ROOT"
    $cmd "${args[@]}"
    
    if [ $? -eq 0 ]; then
        print_success "News fetch completed successfully"
        show_metrics
    else
        print_error "News fetch failed - see logs for details"
        exit 1
    fi
}

# Main command handler
case "${1:-run}" in
    run)
        shift || true
        run_fetch "$@"
        ;;
    ngx)
        shift || true
        run_fetch --ngx-only "$@"
        ;;
    businessday)
        shift || true
        run_fetch --businessday-only "$@"
        ;;
    sentiment)
        print_header "Running Sentiment Analysis"
        cd "$PROJECT_ROOT"
        python -m data.pipeline sentiment-summary
        print_success "Sentiment analysis complete"
        ;;
    test)
        print_header "Running Test Fetch (5 articles max)"
        shift || true
        run_fetch --max-articles 5 "$@"
        ;;
    parallel)
        print_header "Running with Parallel Execution"
        shift || true
        run_fetch --parallel "$@"
        ;;
    logs)
        show_logs
        ;;
    metrics)
        show_metrics
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac

exit 0
