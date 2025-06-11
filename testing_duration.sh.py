#!/bin/bash

SEARCH_TERM="channel: testing"
THRESHOLD_DAYS=90

FILES=$(rg -l "$SEARCH_TERM" -g '*.yaml' -g '!**/archived/**' rules/default rules/sanctioned rules/ueba)

printf "%-60s | %-20s | %-5s | %-15s | %-15s\n" "File" "Date Added" "Days" "Referenced?" "Building Block"
printf -- '%.0s-' {1..125}; echo

for file in $FILES; do
    commit_hash=$(git log --reverse -S"$SEARCH_TERM" --format='%H' -- "$file" | head -n1)
    [ -z "$commit_hash" ] && continue

    commit_date=$(git show -s --format='%ci' "$commit_hash")

    # macOS date calc
    days_ago=$(( ( $(date +%s) - $(date -j -f "%Y-%m-%d %H:%M:%S %z" "$commit_date" "+%s") ) / (60*60*24) ))
    # Linux alternative (uncomment if using Linux)
    # days_ago=$(( ( $(date +%s) - $(date -d "$commit_date" "+%s") ) / (60*60*24) ))

    if [ "$days_ago" -gt "$THRESHOLD_DAYS" ]; then
        # Extract this file's ID
        id=$(grep '^id:' "$file" | awk '{print $2}' | tr -d '"')

        # Check for references by non-testing, raise_alert:true rules
        referenced_by=$(rg -l "$id" -g '*.yaml' -g '!**/archived/**' rules/default rules/sanctioned rules/ueba \
                        | xargs grep -L "channel: testing" \
                        | xargs grep -l "raise_alert: true")

        [ -n "$referenced_by" ] && ref_status="✅ Yes" || ref_status="❌ No"

        # Check if building_block is true or false
        building_block=$(grep '^building_block:' "$file" | awk '{print $2}' | tr -d '"')

        [ "$building_block" == "true" ] && bb_status="✅ True" || bb_status="❌ False"

        printf "%-60s | %-20s | %-5s | %-15s | %-15s\n" "$(basename "$file")" "$commit_date" "$days_ago" "$ref_status" "$bb_status"
    fi
done
