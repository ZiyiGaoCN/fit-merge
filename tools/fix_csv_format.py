#!/usr/bin/env python3
import re

def fix_csv_format(input_file, output_file):
    """Fix pandas-generated CSV to match official Garmin format"""
    print(f"Fixing CSV format: {input_file} -> {output_file}")
    
    # Read the file as text to preserve exact formatting
    with open(input_file, 'r') as f:
        content = f.read()
    
    # Remove .0 from integer values in the CSV
    # This regex finds patterns like "115.0" and replaces with "115"
    content = re.sub(r'\b(\d+)\.0\b', r'\1', content)
    
    # Remove any trailing commas and extra columns that pandas might have added
    lines = content.split('\n')
    fixed_lines = []
    
    for line in lines:
        if line.strip():
            # Remove trailing empty columns (pandas sometimes adds these)
            while line.endswith(','):
                line = line[:-1]
            
            # Remove unnamed columns
            if 'Unnamed:' in line:
                parts = line.split(',')
                filtered_parts = []
                for part in parts:
                    if not part.startswith('Unnamed:') and part.strip():
                        filtered_parts.append(part)
                line = ','.join(filtered_parts)
            
            fixed_lines.append(line)
    
    # Write fixed content
    with open(output_file, 'w') as f:
        f.write('\n'.join(fixed_lines))
    
    print(f"Fixed CSV saved: {output_file}")

if __name__ == "__main__":
    input_file = "/Users/hfadmin/Library/Mobile Documents/com~apple~CloudDocs/fit merge/merged_official.csv"
    output_file = "/Users/hfadmin/Library/Mobile Documents/com~apple~CloudDocs/fit merge/merged_official_fixed.csv"
    
    fix_csv_format(input_file, output_file)