#!/bin/bash

# AI RADAR - Monitoring Dashboard
# Run this to see real-time system status

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

# Utility functions
clear_screen() {
    clear
}

print_header() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  ${CYAN}$1${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
}

get_status() {
    local service=$1
    if docker-compose ps "$service" 2>/dev/null | grep -q "Up"; then
        echo -e "${GREEN}●${NC} UP"
    elif docker-compose ps "$service" 2>/dev/null | grep -q "Exited"; then
        echo -e "${RED}●${NC} DOWN"
    else
        echo -e "${YELLOW}●${NC} UNKNOWN"
    fi
}

get_memory() {
    docker stats --no-stream "$1" 2>/dev/null | tail -1 | awk '{print $7}' || echo "N/A"
}

get_cpu() {
    docker stats --no-stream "$1" 2>/dev/null | tail -1 | awk '{print $3}' || echo "N/A"
}

# Main dashboard loop
show_dashboard() {
    while true; do
        clear_screen
        
        print_header "AI RADAR - MONITORING DASHBOARD"
        
        # System Time
        echo -e "${MAGENTA}System Time:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
        echo ""
        
        # Services Status
        echo -e "${MAGENTA}Services Status:${NC}"
        echo "┌─────────────────────────────────────────────────────────────┐"
        
        # Check each service
        local api_status=$(get_status "api")
        local db_status=$(get_status "db")
        local redis_status=$(get_status "redis")
        local worker_status=$(get_status "worker")
        local beat_status=$(get_status "beat")
        
        echo -e "  API Server     $(printf '%-45s' "$api_status")"
        echo -e "  Database       $(printf '%-45s' "$db_status")"
        echo -e "  Redis Cache    $(printf '%-45s' "$redis_status")"
        echo -e "  Worker         $(printf '%-45s' "$worker_status")"
        echo -e "  Beat Scheduler $(printf '%-45s' "$beat_status")"
        echo "└─────────────────────────────────────────────────────────────┘"
        echo ""
        
        # Resource Usage
        echo -e "${MAGENTA}Resource Usage:${NC}"
        echo "┌─────────────────────────────────────────────────────────────┐"
        
        echo -e "  Service         CPU         Memory"
        echo "  ──────────────────────────────────────────────────────────"
        
        docker stats --no-stream 2>/dev/null | tail -5 | while read line; do
            if [ -n "$line" ]; then
                service=$(echo "$line" | awk '{print $1}')
                cpu=$(echo "$line" | awk '{print $3}')
                memory=$(echo "$line" | awk '{print $7}')
                printf "  %-15s %-11s %s\n" "$service" "$cpu" "$memory"
            fi
        done
        
        echo "└─────────────────────────────────────────────────────────────┘"
        echo ""
        
        # API Health
        echo -e "${MAGENTA}API Health:${NC}"
        echo "┌─────────────────────────────────────────────────────────────┐"
        
        local health=$(curl -s http://localhost:8000/health 2>/dev/null || echo "UNREACHABLE")
        if echo "$health" | grep -q "ok"; then
            echo -e "  Status: ${GREEN}✓ Healthy${NC}"
        else
            echo -e "  Status: ${RED}✗ Unhealthy${NC}"
        fi
        
        echo "└─────────────────────────────────────────────────────────────┘"
        echo ""
        
        # Database Stats
        echo -e "${MAGENTA}Database Stats:${NC}"
        echo "┌─────────────────────────────────────────────────────────────┐"
        
        local db_size=$(docker-compose exec -T db psql -U aidar -d ai_radar -t -c \
            "SELECT pg_size_pretty(pg_database_size('ai_radar'));" 2>/dev/null || echo "N/A")
        local user_count=$(docker-compose exec -T db psql -U aidar -d ai_radar -t -c \
            "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "0")
        local article_count=$(docker-compose exec -T db psql -U aidar -d ai_radar -t -c \
            "SELECT COUNT(*) FROM articles;" 2>/dev/null || echo "0")
        
        printf "  Database Size:  %-45s\n" "$db_size"
        printf "  Total Users:    %-45s\n" "$user_count"
        printf "  Total Articles: %-45s\n" "$article_count"
        
        echo "└─────────────────────────────────────────────────────────────┘"
        echo ""
        
        # Recent Logs
        echo -e "${MAGENTA}Recent Activity (Last 10 lines):${NC}"
        echo "┌─────────────────────────────────────────────────────────────┐"
        
        docker-compose logs --tail=10 2>/dev/null | tail -10 | sed 's/^/  /'
        
        echo "└─────────────────────────────────────────────────────────────┘"
        echo ""
        
        # Controls
        echo -e "${YELLOW}Controls:${NC}"
        echo "  r - Refresh (auto-refreshes every 5 seconds)"
        echo "  l - Show full logs"
        echo "  s - Show service status"
        echo "  c - Clear and refresh"
        echo "  q - Quit"
        echo ""
        
        # Auto-refresh in 5 seconds or wait for input
        echo -e "${CYAN}Next refresh in 5 seconds... (press q to quit)${NC}"
        
        read -t 5 -n 1 key || key=""
        
        case $key in
            q|Q)
                echo -e "\n${GREEN}Goodbye!${NC}"
                exit 0
                ;;
            l|L)
                clear_screen
                echo -e "${CYAN}=== FULL LOGS ===${NC}\n"
                docker-compose logs --tail=50
                echo -e "\n${CYAN}(Press Enter to return to dashboard)${NC}"
                read
                ;;
            s|S)
                clear_screen
                echo -e "${CYAN}=== SERVICE STATUS ===${NC}\n"
                docker-compose ps
                echo -e "\n${CYAN}(Press Enter to return to dashboard)${NC}"
                read
                ;;
            c|C)
                continue
                ;;
            *)
                continue
                ;;
        esac
    done
}

# Start dashboard
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: docker-compose not found${NC}"
    exit 1
fi

if ! docker-compose ps 2>/dev/null | grep -q "NAME"; then
    echo -e "${RED}Error: Services not running. Start with: docker-compose up -d${NC}"
    exit 1
fi

show_dashboard
