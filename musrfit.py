#!/usr/bin/env python3
import os
import sys
import json
import glob
import csv
import re
import argparse
import subprocess

# --- FIX 1: Dynamically compute the script's root directory ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Add the script directory to the Python path so "src" imports work anywhere
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from src.cxx_plugin_generator import CxxPluginGenerator
from src.msr_generator import MsrGenerator
from src.root_metadata_extractor import extract_root_metadata
from src.plot_musr import plot_musrfit_data, plot_parameters_vs_variable

def cleanup_previous_runs():
    """Removes previously generated data files to ensure a clean run environment."""
    print(">> Cleaning up previous run outputs (*.csv, *.dat, *.pdf)...")
    for ext in ['*.csv', '*.dat', '*.pdf']:
        for file_path in glob.glob(ext):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"   [!] Warning: Could not remove {file_path}: {e}")

def export_msr_to_split_csvs(msr_filepath, data_files, config):
    """Parses a completed MSR file and exports variables into separated CSV targets."""
    if not os.path.exists(msr_filepath):
        print(f"[!] Warning: Cannot locate {msr_filepath} to export CSV benchmarks.")
        return

    suffix_mapping = config.get("suffix_mapping", {})
    var_name = suffix_mapping.get("variable_name", "Variable")
    mapping = suffix_mapping.get("mapping", {})
    fittype = config.get("fittype", 2)
    num_detectors = len(config.get("detectors", {})) if fittype == 0 else 1

    all_params = []
    in_fit_params = False

    with open(msr_filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith("FITPARAMETER"):
                in_fit_params = True
                continue

            if in_fit_params:
                if line == "" or line.startswith("THEORY") or line.startswith("###"):
                    break
                if line.startswith("#"):
                    continue

                parts = re.split(r'\s+', line)
                if len(parts) >= 4:
                    param_dict = {
                        "No": parts[0],
                        "Name": parts[1],
                        "Value": parts[2],
                        "Step/Error": parts[3],
                        "Pos_Error": parts[4] if len(parts) > 4 else "none",
                        "Bound_Low": parts[5] if len(parts) > 5 else "none",
                        "Bound_High": parts[6] if len(parts) > 6 else "none"
                    }
                    all_params.append(param_dict)

    if not all_params:
        print(f"[!] No fit parameters found in {msr_filepath}.")
        return

    global_rows = []
    local_groups = {}

    for p in all_params:
        name = p["Name"]
        match_run = re.search(r"^(.*)_Run(\d+)(?:_(.*))?$", name)
        match_file = re.search(r"^(.*)_File(\d+)$", name)
        
        if match_run:
            base_param_name = match_run.group(1)
            run_idx = int(match_run.group(2)) - 1
            det_name = match_run.group(3) if match_run.group(3) else ""
            file_idx = run_idx // num_detectors if fittype == 0 else run_idx
            
            var_val = "Unknown"
            if 0 <= file_idx < len(data_files):
                filename = data_files[file_idx]
                for suffix, s_val in mapping.items():
                    if suffix in filename:
                        var_val = s_val
                        break

            local_row = {
                "Run_Index": run_idx + 1,
                "Detector": det_name if det_name else "Combined",
                "File_Name": data_files[file_idx] if 0 <= file_idx < len(data_files) else "Unknown",
                var_name: var_val,
                "Value": p["Value"],
                "Step/Error": p["Step/Error"],
                "Pos_Error": p["Pos_Error"],
                "Bound_Low": p["Bound_Low"],
                "Bound_High": p["Bound_High"]
            }
            if base_param_name not in local_groups:
                local_groups[base_param_name] = []
            local_groups[base_param_name].append(local_row)
            
            p["BaseName"] = base_param_name
            p["Variable_Value"] = var_val
            
        elif match_file:
            base_param_name = match_file.group(1)
            file_idx = int(match_file.group(2)) - 1
            
            var_val = "Unknown"
            if 0 <= file_idx < len(data_files):
                filename = data_files[file_idx]
                for suffix, s_val in mapping.items():
                    if suffix in filename:
                        var_val = s_val
                        break

            local_row = {
                "Run_Index": f"File_{file_idx + 1}",
                "Detector": "All",
                "File_Name": data_files[file_idx] if 0 <= file_idx < len(data_files) else "Unknown",
                var_name: var_val,
                "Value": p["Value"],
                "Step/Error": p["Step/Error"],
                "Pos_Error": p["Pos_Error"],
                "Bound_Low": p["Bound_Low"],
                "Bound_High": p["Bound_High"]
            }
            if base_param_name not in local_groups:
                local_groups[base_param_name] = []
            local_groups[base_param_name].append(local_row)
            
            p["BaseName"] = base_param_name
            p["Variable_Value"] = var_val
        else:
            global_rows.append(p)
            p["BaseName"] = p["Name"]
            p["Variable_Value"] = "Global"

    global_csv_path = "global_parameters.csv"
    with open(global_csv_path, 'w', newline='') as csvfile:
        fieldnames = ["No", "Name", "Value", "Step/Error", "Pos_Error", "Bound_Low", "Bound_High"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in global_rows:
            filtered_row = {k: row[k] for k in fieldnames if k in row}
            writer.writerow(filtered_row)
    print(f">> Exported global fit parameters to '{global_csv_path}'")

    for base_name, rows in local_groups.items():
        local_csv_path = f"local_parameter_{base_name}.csv"
        with open(local_csv_path, 'w', newline='') as csvfile:
            fieldnames = ["Run_Index", "Detector", "File_Name", var_name, "Value", "Step/Error", "Pos_Error", "Bound_Low", "Bound_High"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                filtered_row = {k: row[k] for k in fieldnames if k in row}
                writer.writerow(filtered_row)
        print(f">> Exported tracking sheet to '{local_csv_path}'")

    if mapping:
        plot_parameters_vs_variable(all_params, var_name)


def run_orchestration_pipeline(config_file="config.json", output_msr="fit_model.msr", do_plot=False):
    # Perform cleanup of old results
    cleanup_previous_runs()

    if config_file == "config.json" and not os.path.exists(config_file):
        config_file = os.path.join(SCRIPT_DIR, "config.json")

    if not os.path.exists(config_file):
        print(f"[!] Fatal: Configuration file '{config_file}' not found.")
        return
        
    with open(config_file, 'r') as f:
        config = json.load(f)
        
    run_format = config.get("instrument", {}).get("format", "MUD").upper()
    extension_map = {
        "MUD": ".msr", "NEXUS": ".nxs", "ROOT": ".root",
        "MUSRROOT": ".root", "MUSR-ROOT": ".root", "PSI-BIN": ".bin"
    }
    target_extension = extension_map.get(run_format, ".root")
    
    data_files = sorted(glob.glob(f"*{target_extension}"))
    data_files = [f for f in data_files if f != "MINUIT2.root"]
    
    suffix_mapping = config.get("suffix_mapping", {})
    var_name = suffix_mapping.get("variable_name")
    mapping = suffix_mapping.get("mapping", {})

    if mapping:
        filtered_files = []
        for f in data_files:
            if any(suffix in f for suffix in mapping):
                filtered_files.append(f)
        data_files = filtered_files
        print(f">> Active dataset filtered via suffix_mapping: {len(data_files)} files retained for analysis.")

    if not data_files:
        print(f"[!] Info: No matching data collections found or retained using '{target_extension}' in current directory.")
        return
    
    if "timing" in config and config["timing"]:
        print(f">> Honoring timing constraints directly from '{config_file}' configuration.")
        for scope in ["forward", "backward"]:
            if f"bkg_range_{scope}" not in config["timing"]:
                config["timing"][f"bkg_range_{scope}"] = config["timing"].get("bkg_range", [0, 0])
            if f"data_range_{scope}" not in config["timing"]:
                config["timing"][f"data_range_{scope}"] = config["timing"].get("data_range", [0, 0])
    else:
        print(f">> Timing block missing or empty in configuration. Falling back to metadata extraction...")
        metadata = extract_root_metadata(data_files[0])
        if metadata.get("success"):
            config["timing"] = metadata
        else:
            print(f"   [!] Error: Timing could not be determined. Check your configuration file layout.")
            return
        
    for custom_cfg in config.get("custom_definitions", []):
        CxxPluginGenerator.generate_and_compile(custom_cfg)
        
    generator = MsrGenerator(config, data_files)
    msr_text_blob = generator.generate_msr_string()
    
    with open(output_msr, 'w') as f:
        f.write(msr_text_blob)
    print(f">> Complete orchestration blueprint logged to '{output_msr}'.")
    
    print(f">> Triggering active analysis handoff wrapper step...")
    try:
        subprocess.run(["musrfit", "--dump", "ascii", output_msr], check=True)
    except subprocess.CalledProcessError as e:
        print(f"[!] Error occurred during musrfit execution: {e}")

    export_msr_to_split_csvs(output_msr, data_files, config)

    if do_plot:
        print(f">> Rendering data visualization plots...")
        base_name = os.path.splitext(output_msr)[0]
        dat_files = sorted(glob.glob(f"{base_name}_*.dat"))
        
        if not dat_files:
            print(f"[!] No ASCII dump files found matching '{base_name}_*.dat'. Ensure musrfit ran successfully.")
        else:
            fittype = config.get("fittype", 2)
            num_detectors = len(config.get("detectors", {})) if fittype == 0 else 1
            for i, dat_file in enumerate(dat_files):
                pdf_name = dat_file.replace(".dat", ".pdf")
                file_idx = i // num_detectors
                
                var_val = None
                if file_idx < len(data_files) and mapping:
                    filename = data_files[file_idx]
                    for suffix, s_val in mapping.items():
                        if suffix in filename:
                            var_val = s_val
                            break
                            
                plot_musrfit_data(dat_file, pdf_name, variable_name=var_name, variable_value=var_val)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated muSR Fitting Orchestrator")
    parser.add_argument("-c", "--config", type=str, default="config.json")
    parser.add_argument("-p", "--plot", action="store_true")
    
    args = parser.parse_args()
    run_orchestration_pipeline(config_file=args.config, output_msr="fit_model.msr", do_plot=args.plot)