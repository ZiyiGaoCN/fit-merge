#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import shutil

def find_fit_csv_tool():
    """Find the FitCSVTool.jar in common locations"""
    possible_paths = [
        "FitSDK/java/FitCSVTool.jar",
        "../FitSDK/java/FitCSVTool.jar", 
        "./FitCSVTool.jar",
        os.path.expanduser("~/FitSDK/java/FitCSVTool.jar"),
        "/opt/FitSDK/java/FitCSVTool.jar"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

def convert_fit_to_csv(fit_file_path, csv_file_path, fit_csv_tool_path):
    """Convert FIT file to CSV using official Garmin FitCSVTool"""
    print(f"Converting {os.path.basename(fit_file_path)} to CSV...")
    
    try:
        # Run the Java FitCSVTool
        cmd = [
            "java", "-jar", fit_csv_tool_path,
            "-b",  # Use -b for binary input
            fit_file_path,
            csv_file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if os.path.exists(csv_file_path):
            # Count lines in CSV to report record count
            with open(csv_file_path, 'r') as f:
                line_count = sum(1 for line in f) - 1  # Subtract header
            print(f"  Successfully converted to {os.path.basename(csv_file_path)} ({line_count} records)")
            return line_count
        else:
            print(f"  Warning: CSV file was not created")
            return 0
            
    except subprocess.CalledProcessError as e:
        print(f"  Error converting {os.path.basename(fit_file_path)}: {e.stderr}")
        return 0
    except Exception as e:
        print(f"  Error converting {os.path.basename(fit_file_path)}: {e}")
        return 0

def check_java():
    """Check if Java is available"""
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def convert_specified_fit_files(fit_files, fit_csv_tool_path, output_path=None):
    """Convert specified FIT files to CSV using official FitCSVTool"""
    print(f"Converting {len(fit_files)} FIT files:")
    
    for fit_file in fit_files:
        print(f"  - {os.path.basename(fit_file)}")
    
    print("\n" + "="*50)
    
    # Convert each file to CSV
    conversion_results = {}
    
    for fit_file in fit_files:
        if not os.path.exists(fit_file):
            print(f"Error: File {fit_file} does not exist")
            continue
            
        # Generate CSV filename based on output option
        if output_path:
            if len(fit_files) == 1 and not os.path.isdir(output_path):
                # Single file and output is not a directory - use as filename
                csv_file = output_path
                if not csv_file.endswith('.csv'):
                    csv_file += '.csv'
            else:
                # Multiple files or output is directory - put CSV in output directory
                if not os.path.exists(output_path):
                    os.makedirs(output_path, exist_ok=True)
                base_name = os.path.splitext(os.path.basename(fit_file))[0]
                csv_file = os.path.join(output_path, f"{base_name}.csv")
        else:
            # Default: same directory as FIT file
            base_name = os.path.splitext(fit_file)[0]
            csv_file = f"{base_name}.csv"
        
        # Convert using official FitCSVTool
        record_count = convert_fit_to_csv(fit_file, csv_file, fit_csv_tool_path)
        
        conversion_results[fit_file] = {
            'csv_file': csv_file,
            'record_count': record_count
        }
    
    print("\n" + "="*50)
    print("Conversion Summary:")
    for fit_file, result in conversion_results.items():
        fit_name = os.path.basename(fit_file)
        csv_name = os.path.basename(result['csv_file'])
        print(f"  {fit_name} -> {csv_name} ({result['record_count']} records)")
    
    return conversion_results

def main():
    parser = argparse.ArgumentParser(description='Convert FIT files to CSV format using official Garmin FitCSVTool')
    parser.add_argument('files', nargs='+', help='FIT files to convert')
    parser.add_argument('--tool-path', '-t', help='Path to FitCSVTool.jar')
    parser.add_argument('--output', '-o', help='Output file or directory. For single file: output.csv. For multiple files: output directory')
    
    args = parser.parse_args()
    
    # Check if Java is available
    if not check_java():
        print("Error: Java is not available. Please install Java to use FitCSVTool.")
        sys.exit(1)
    
    # Find FitCSVTool.jar
    fit_csv_tool_path = args.tool_path or find_fit_csv_tool()
    
    if not fit_csv_tool_path:
        print("Error: FitCSVTool.jar not found. Please provide path with --tool-path")
        print("Expected locations:")
        print("  - FitSDK/java/FitCSVTool.jar")
        print("  - ../FitSDK/java/FitCSVTool.jar")
        print("  - ./FitCSVTool.jar")
        print("  - ~/FitSDK/java/FitCSVTool.jar")
        sys.exit(1)
    
    print(f"Using FitCSVTool: {fit_csv_tool_path}")
    
    # Validate that all files exist and are .fit files
    valid_files = []
    for file_path in args.files:
        if not os.path.exists(file_path):
            print(f"Error: File {file_path} does not exist")
            continue
        if not file_path.lower().endswith('.fit'):
            print(f"Warning: {file_path} does not appear to be a FIT file")
        valid_files.append(file_path)
    
    if not valid_files:
        print("No valid files to process")
        sys.exit(1)
    
    results = convert_specified_fit_files(valid_files, fit_csv_tool_path, args.output)
    print(f"\nConversion completed! {len(results)} files processed.")

if __name__ == "__main__":
    main()