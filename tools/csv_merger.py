#!/usr/bin/env python3
import os
import csv
import struct
import pandas as pd
from datetime import datetime, timedelta
from fitparse import FitFile

def fit_to_csv(fit_file_path, csv_file_path):
    """Convert FIT file to CSV format"""
    print(f"Converting {fit_file_path} to CSV...")
    
    fit_file = FitFile(fit_file_path)
    records = []
    
    for record in fit_file.get_messages('record'):
        row = {}
        for field in record.fields:
            if field.value is not None:
                if isinstance(field.value, datetime):
                    row[field.name] = field.value.isoformat()
                else:
                    row[field.name] = field.value
        if row:  # Only add non-empty records
            records.append(row)
    
    if records:
        df = pd.DataFrame(records)
        df.to_csv(csv_file_path, index=False)
        print(f"Exported {len(records)} records to {csv_file_path}")
        return len(records)
    else:
        print("No records found in FIT file")
        return 0

def merge_csv_files(csv1_path, csv2_path, merged_csv_path):
    """Merge two CSV files with proper deduplication and sorting"""
    print(f"Merging CSV files...")
    
    # Read both CSV files
    df1 = pd.read_csv(csv1_path)
    df2 = pd.read_csv(csv2_path)
    
    print(f"CSV 1: {len(df1)} records")
    print(f"CSV 2: {len(df2)} records")
    
    # Combine dataframes
    combined_df = pd.concat([df1, df2], ignore_index=True)
    
    # Convert timestamp column back to datetime for sorting
    if 'timestamp' in combined_df.columns:
        combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp'])
        # Sort by timestamp
        combined_df = combined_df.sort_values('timestamp')
        # Remove duplicates based on timestamp
        combined_df = combined_df.drop_duplicates(subset=['timestamp'], keep='first')
        # Convert back to ISO format for CSV
        combined_df['timestamp'] = combined_df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S')
    
    # Save merged CSV
    combined_df.to_csv(merged_csv_path, index=False)
    print(f"Merged CSV saved with {len(combined_df)} records")
    
    return len(combined_df)

def csv_to_fit(csv_file_path, fit_file_path):
    """Convert CSV back to FIT format using reference structure"""
    print(f"Converting CSV back to FIT format...")
    
    # Read CSV data
    df = pd.read_csv(csv_file_path)
    print(f"Converting {len(df)} records from CSV to FIT")
    
    # Read reference file to understand structure
    reference_path = "/Users/hfadmin/Library/Mobile Documents/com~apple~CloudDocs/fit merge/gpxt_result.fit"
    ref_fit = FitFile(reference_path)
    
    # Read reference file binary data to use as template
    with open(reference_path, 'rb') as ref_file:
        ref_data = ref_file.read()
    
    # Extract header from reference
    ref_header_size = ref_data[0]
    ref_header = ref_data[:ref_header_size]
    
    # Get reference record structure
    ref_records = []
    for record in ref_fit.get_messages('record'):
        ref_records.append(record)
    
    if not ref_records:
        raise ValueError("No reference records found")
    
    # Analyze reference record structure
    sample_record = ref_records[0]
    field_definitions = []
    
    # Map common field types and sizes
    field_map = {
        'timestamp': {'def_num': 253, 'size': 4, 'base_type': 134},  # uint32
        'position_lat': {'def_num': 0, 'size': 4, 'base_type': 134},  # sint32
        'position_long': {'def_num': 1, 'size': 4, 'base_type': 134},  # sint32
        'altitude': {'def_num': 2, 'size': 2, 'base_type': 132},  # uint16
        'heart_rate': {'def_num': 3, 'size': 1, 'base_type': 2},   # uint8
        'cadence': {'def_num': 4, 'size': 1, 'base_type': 2},      # uint8
        'distance': {'def_num': 5, 'size': 4, 'base_type': 134},   # uint32
        'speed': {'def_num': 6, 'size': 2, 'base_type': 132},      # uint16
        'power': {'def_num': 7, 'size': 2, 'base_type': 132},      # uint16
        'temperature': {'def_num': 13, 'size': 1, 'base_type': 1}, # sint8
    }
    
    # Build field definitions based on available CSV columns
    for col in df.columns:
        if col in field_map:
            field_definitions.append(field_map[col])
    
    # Create FIT data
    fit_data = bytearray()
    
    # Write definition message for record (global message number 20)
    def_header = 0x40  # Definition message flag
    fit_data.append(def_header)
    fit_data.append(0)  # Reserved
    fit_data.append(0)  # Architecture (little endian)
    fit_data.extend(struct.pack('<H', 20))  # Global message number for record
    fit_data.append(len(field_definitions))  # Number of fields
    
    # Write field definitions
    for field_def in field_definitions:
        fit_data.append(field_def['def_num'])
        fit_data.append(field_def['size'])
        fit_data.append(field_def['base_type'])
    
    # Convert CSV records to FIT data messages
    for _, row in df.iterrows():
        # Data message header (local message type 0)
        fit_data.append(0x00)
        
        # Write field data
        for col in df.columns:
            if col in field_map:
                value = row[col]
                field_info = field_map[col]
                
                if pd.isna(value):
                    # Write invalid value
                    fit_data.extend(b'\xFF' * field_info['size'])
                    continue
                
                if col == 'timestamp':
                    # Convert ISO timestamp to FIT timestamp (seconds since UTC 00:00 Dec 31 1989)
                    dt = pd.to_datetime(value)
                    fit_epoch = datetime(1989, 12, 31)
                    fit_timestamp = int((dt - fit_epoch).total_seconds())
                    fit_data.extend(struct.pack('<I', fit_timestamp))
                
                elif col in ['position_lat', 'position_long']:
                    # Convert to semicircles (degrees * 2^31 / 180)
                    if value != 0 and not pd.isna(value):
                        semicircles = int(value * (2**31) / 180)
                        # Clamp to valid int32 range
                        semicircles = max(-2147483648, min(2147483647, semicircles))
                        fit_data.extend(struct.pack('<i', semicircles))
                    else:
                        fit_data.extend(struct.pack('<i', 0x7FFFFFFF))  # Invalid
                
                elif field_info['base_type'] == 134:  # uint32
                    if field_info['size'] == 4:
                        fit_data.extend(struct.pack('<I', int(value) if not pd.isna(value) else 0xFFFFFFFF))
                
                elif field_info['base_type'] == 132:  # uint16
                    if field_info['size'] == 2:
                        fit_data.extend(struct.pack('<H', int(value) if not pd.isna(value) else 0xFFFF))
                
                elif field_info['base_type'] == 2:  # uint8
                    if field_info['size'] == 1:
                        fit_data.extend(struct.pack('<B', int(value) if not pd.isna(value) else 0xFF))
                
                elif field_info['base_type'] == 1:  # sint8
                    if field_info['size'] == 1:
                        fit_data.extend(struct.pack('<b', int(value) if not pd.isna(value) else 0x7F))
    
    # Create final FIT file
    # Use reference header but update data size
    new_header = bytearray(ref_header)
    new_header[4:8] = struct.pack('<I', len(fit_data))
    
    # Calculate header CRC
    def calculate_crc(data):
        crc_table = [
            0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
            0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400
        ]
        crc = 0
        for byte in data:
            tmp = crc_table[crc & 0xF]
            crc = (crc >> 4) & 0x0FFF
            crc = crc ^ tmp ^ crc_table[byte & 0xF]
            tmp = crc_table[crc & 0xF]
            crc = (crc >> 4) & 0x0FFF
            crc = crc ^ tmp ^ crc_table[(byte >> 4) & 0xF]
        return crc
    
    header_crc = calculate_crc(new_header[:12])
    new_header[12:14] = struct.pack('<H', header_crc)
    
    # Calculate data CRC
    data_crc = calculate_crc(fit_data)
    
    # Write final file
    with open(fit_file_path, 'wb') as output_file:
        output_file.write(new_header)
        output_file.write(fit_data)
        output_file.write(struct.pack('<H', data_crc))
    
    print(f"FIT file created: {fit_file_path}")
    print(f"Total size: {len(new_header) + len(fit_data) + 2} bytes")
    
    return fit_file_path

def merge_fit_via_csv(file1_path, file2_path, output_path):
    """Complete FIT merge workflow via CSV"""
    base_path = os.path.dirname(file1_path)
    
    # Step 1: Convert FIT files to CSV
    csv1_path = os.path.join(base_path, "temp_file1.csv")
    csv2_path = os.path.join(base_path, "temp_file2.csv")
    merged_csv_path = os.path.join(base_path, "temp_merged.csv")
    
    try:
        # Convert both FIT files to CSV
        records1 = fit_to_csv(file1_path, csv1_path)
        records2 = fit_to_csv(file2_path, csv2_path)
        
        if records1 == 0 and records2 == 0:
            print("No records found in either file")
            return None
        
        # Merge CSV files
        total_records = merge_csv_files(csv1_path, csv2_path, merged_csv_path)
        
        # Convert merged CSV back to FIT
        result_path = csv_to_fit(merged_csv_path, output_path)
        
        print(f"\n=== Merge Complete ===")
        print(f"Input 1: {records1} records")
        print(f"Input 2: {records2} records")
        print(f"Merged: {total_records} records")
        print(f"Output: {result_path}")
        
        return result_path
        
    finally:
        # Clean up temporary files
        for temp_file in [csv1_path, csv2_path, merged_csv_path]:
            if os.path.exists(temp_file):
                os.remove(temp_file)

if __name__ == "__main__":
    base_path = "/Users/hfadmin/Library/Mobile Documents/com~apple~CloudDocs/fit merge"
    
    file1 = os.path.join(base_path, "ride-0-2025-07-19-09-41-59.fit")
    file2 = os.path.join(base_path, "ride-0-2025-07-19-14-53-44.fit")
    output = os.path.join(base_path, "csv_merged.fit")
    
    # Perform the merge
    result = merge_fit_via_csv(file1, file2, output)
    
    if result:
        # Verify the result
        try:
            result_fit = FitFile(result)
            result_records = [r for r in result_fit.get_messages('record')]
            
            print(f"\n=== Verification ===")
            print(f"Final FIT file has {len(result_records)} records")
            
            if result_records:
                first_time = result_records[0].get_value('timestamp')
                last_time = result_records[-1].get_value('timestamp')
                print(f"Time range: {first_time} to {last_time}")
                
                # Check for proper time ordering
                timestamps = [r.get_value('timestamp') for r in result_records if r.get_value('timestamp')]
                is_sorted = all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1))
                print(f"Records properly sorted: {is_sorted}")
                
        except Exception as e:
            print(f"Error verifying result: {e}")
    else:
        print("Merge failed")