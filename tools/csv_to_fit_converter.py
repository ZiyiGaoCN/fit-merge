#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess

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

def check_java():
    """Check if Java is available"""
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def convert_csv_to_fit(csv_file_path, fit_file_path, fit_csv_tool_path):
    """Convert CSV file to FIT using official Garmin FitCSVTool"""
    print(f"Converting {os.path.basename(csv_file_path)} to FIT...")
    
    try:
        # Run the Java FitCSVTool with -c flag for CSV to FIT conversion
        cmd = [
            "java", "-jar", fit_csv_tool_path,
            "-c",  # Use -c for CSV to FIT conversion
            csv_file_path,
            fit_file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if os.path.exists(fit_file_path):
            file_size = os.path.getsize(fit_file_path)
            print(f"  Successfully converted to {os.path.basename(fit_file_path)} ({file_size} bytes)")
            return True
        else:
            print(f"  Warning: FIT file was not created")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"  Error converting {os.path.basename(csv_file_path)}: {e.stderr}")
        return False
    except Exception as e:
        print(f"  Error converting {os.path.basename(csv_file_path)}: {e}")
        return False


def convert_specified_csv_files(csv_files, fit_csv_tool_path, output_path=None):
    """Convert specified CSV files to FIT format using official FitCSVTool"""
    print(f"Converting {len(csv_files)} CSV files to FIT:")
    
    for csv_file in csv_files:
        print(f"  - {os.path.basename(csv_file)}")
    
    print("\n" + "="*50)
    
    conversion_results = {}
    
    for csv_file in csv_files:
        if not os.path.exists(csv_file):
            print(f"Error: File {csv_file} does not exist")
            continue
            
        # Generate FIT filename based on output option
        if output_path:
            if len(csv_files) == 1 and not os.path.isdir(output_path):
                # Single file and output is not a directory - use as filename
                fit_file = output_path
                if not fit_file.endswith('.fit'):
                    fit_file += '.fit'
            else:
                # Multiple files or output is directory - put FIT in output directory
                if not os.path.exists(output_path):
                    os.makedirs(output_path, exist_ok=True)
                base_name = os.path.splitext(os.path.basename(csv_file))[0]
                fit_file = os.path.join(output_path, f"{base_name}.fit")
        else:
            # Default: same directory as CSV file
            base_name = os.path.splitext(csv_file)[0]
            fit_file = f"{base_name}.fit"
        
        # Convert CSV to FIT using official FitCSVTool
        success = convert_csv_to_fit(csv_file, fit_file, fit_csv_tool_path)
        
        conversion_results[csv_file] = {
            'fit_file': fit_file,
            'success': success
        }
    
    print("\n" + "="*50)
    print("Conversion Summary:")
    for csv_file, result in conversion_results.items():
        csv_name = os.path.basename(csv_file)
        fit_name = os.path.basename(result['fit_file'])
        status = "SUCCESS" if result['success'] else "FAILED"
        print(f"  {csv_name} -> {fit_name} ({status})")
    
    return conversion_results

def main():
    parser = argparse.ArgumentParser(description='Convert CSV files to FIT format using official Garmin FitCSVTool')
    parser.add_argument('files', nargs='+', help='CSV files to convert')
    parser.add_argument('--tool-path', '-t', help='Path to FitCSVTool.jar')
    parser.add_argument('--output', '-o', help='Output file or directory. For single file: output.fit. For multiple files: output directory')
    
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
    
    # Validate that all files exist and are .csv files
    valid_files = []
    for file_path in args.files:
        if not os.path.exists(file_path):
            print(f"Error: File {file_path} does not exist")
            continue
        if not file_path.lower().endswith('.csv'):
            print(f"Warning: {file_path} does not appear to be a CSV file")
        valid_files.append(file_path)
    
    if not valid_files:
        print("No valid files to process")
        sys.exit(1)
    
    results = convert_specified_csv_files(valid_files, fit_csv_tool_path, args.output)
    successful = sum(1 for r in results.values() if r['success'])
    print(f"\nConversion completed! {successful}/{len(results)} files processed successfully.")

if __name__ == "__main__":
    main()