#!/usr/bin/env python3
import pandas as pd
import os
from datetime import datetime

def merge_official_csv_files(csv1_path, csv2_path, output_path):
    """Merge two official Garmin CSV files properly"""
    print(f"Merging {os.path.basename(csv1_path)} and {os.path.basename(csv2_path)}")
    
    # Read both CSV files
    df1 = pd.read_csv(csv1_path)
    df2 = pd.read_csv(csv2_path)
    
    print(f"File 1: {len(df1)} rows")
    print(f"File 2: {len(df2)} rows")
    
    # Combine dataframes
    merged_df = pd.concat([df1, df2], ignore_index=True)
    
    # Sort by message type and timestamp where applicable
    # First, let's separate by message type
    def get_sort_key(row):
        msg_type = row['Message']
        timestamp = 0
        
        # Find timestamp field
        for i in range(1, 50):  # Check field columns
            field_col = f'Field {i}'
            value_col = f'Value {i}'
            
            if field_col in row and value_col in row:
                if pd.notna(row[field_col]) and row[field_col] == 'timestamp':
                    if pd.notna(row[value_col]):
                        try:
                            timestamp = int(str(row[value_col]).split('|')[0])
                        except:
                            timestamp = 0
                    break
        
        # Sort order: file_id, device_info, then by timestamp
        type_priority = {
            'file_id': 0,
            'device_info': 1,
            'event': 2,
            'record': 3,
            'lap': 4,
            'session': 5,
            'activity': 6
        }
        
        priority = type_priority.get(msg_type, 999)
        return (priority, timestamp)
    
    # Sort the merged data
    merged_df['sort_key'] = merged_df.apply(get_sort_key, axis=1)
    merged_df = merged_df.sort_values('sort_key')
    merged_df = merged_df.drop('sort_key', axis=1)
    
    # Remove duplicate records based on message type and timestamp
    duplicates_removed = 0
    if len(merged_df) > 1:
        # For record messages, check for duplicate timestamps
        record_rows = merged_df[merged_df['Message'] == 'record']
        if len(record_rows) > 1:
            # Extract timestamps for comparison
            timestamps = []
            indices = []
            
            for idx, row in record_rows.iterrows():
                timestamp = None
                for i in range(1, 50):
                    field_col = f'Field {i}'
                    value_col = f'Value {i}'
                    
                    if field_col in row and value_col in row:
                        if pd.notna(row[field_col]) and row[field_col] == 'timestamp':
                            if pd.notna(row[value_col]):
                                try:
                                    timestamp = int(str(row[value_col]).split('|')[0])
                                except:
                                    pass
                            break
                
                if timestamp is not None:
                    timestamps.append(timestamp)
                    indices.append(idx)
            
            # Find duplicates
            seen_timestamps = set()
            duplicate_indices = []
            
            for i, (idx, ts) in enumerate(zip(indices, timestamps)):
                if ts in seen_timestamps:
                    duplicate_indices.append(idx)
                    duplicates_removed += 1
                else:
                    seen_timestamps.add(ts)
            
            # Remove duplicates
            if duplicate_indices:
                merged_df = merged_df.drop(duplicate_indices)
    
    # Save merged file
    merged_df.to_csv(output_path, index=False)
    
    print(f"Merged file saved: {output_path}")
    print(f"Total rows: {len(merged_df)}")
    print(f"Duplicates removed: {duplicates_removed}")
    
    return output_path

if __name__ == "__main__":
    base_path = "/Users/hfadmin/Library/Mobile Documents/com~apple~CloudDocs/fit merge"
    
    csv1 = os.path.join(base_path, "ride1_official.csv")
    csv2 = os.path.join(base_path, "ride2_official.csv")
    merged_csv = os.path.join(base_path, "merged_official.csv")
    
    if os.path.exists(csv1) and os.path.exists(csv2):
        result = merge_official_csv_files(csv1, csv2, merged_csv)
        print(f"\nNext step: Convert back to FIT using:")
        print(f"java -jar java/FitCSVTool.jar -c {os.path.basename(result)} final_merged.fit")
    else:
        print("CSV files not found. Please run the FIT to CSV conversion first.")