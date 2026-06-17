#!/usr/bin/env python3
import os
import sys
import json
import glob
import csv
import re
import argparse
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from src.cxx_plugin_generator import CxxPluginGenerator
from src.msr_generator import MsrGenerator
from src.root_metadata_extractor import build_timing_config
from src.plot_musr import plot_musrfit_data, plot_parameters_vs_variable, plot_reconstructed_asymmetry

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
                # --- FIX: Stop ONLY on Theory/Commands. Ignore empty lines! ---
                if line.startswith("THEORY") or line.startswith("COMMANDS"):
                    break
                if not line or line.startswith("#"):
                    continue

                parts = re.split(r'\s+', line)

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
        print(f"[!] No fit parameters found in {msr_filepath}. Ensure the fit ran successfully.")
        return

    global_rows = []
    file_groups = {}
    local_groups = {}
    params_to_plot = []

    for p in all_params:
        name = p["Name"]
        
        # --- FIX: Case-insensitive, robust regex matching ---
        # Matches: Param_File0364_Run1_forward, Param_file0364_run1
        match_run = re.search(r"^(.*?)_?[Ff]ile(\d+)_?[Rr]un(\d+)(?:_(.+))?$", name)
        # Matches: Param_File0364, Param_file0364
        match_file = re.search(r"^(.*?)_?[Ff]ile(\d+)$", name)
        
        if match_run:
            base_param_name = match_run.group(1)
            file_suffix = match_run.group(2)
            run_idx = int(match_run.group(3)) - 1
            det_name = match_run.group(4) if match_run.group(4) else "Combined"
            
            # --- FIX: Find the correct file index using the extracted file_suffix ---
            file_idx = -1
            for i, fname in enumerate(data_files):
                if file_suffix in fname:
                    file_idx = i
                    break
            
            var_val = "Unknown"
            if 0 <= file_idx < len(data_files):
                filename = data_files[file_idx]
                for suffix, s_val in mapping.items():
                    if suffix in filename:
                        var_val = s_val
                        break

            local_row = {
                "Run_Index": run_idx + 1,
                "Detector": det_name,
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
            
            if fittype == 2:
                params_to_plot.append(p)
            
        elif match_file:
            base_param_name = match_file.group(1)
            file_suffix = match_file.group(2)
            
            # --- FIX: Find the correct file index using the extracted file_suffix ---
            file_idx = -1
            for i, fname in enumerate(data_files):
                if file_suffix in fname:
                    file_idx = i
                    break
            
            var_val = "Unknown"
            if 0 <= file_idx < len(data_files):
                filename = data_files[file_idx]
                for suffix, s_val in mapping.items():
                    if suffix in filename:
                        var_val = s_val
                        break

            file_row = {
                "File_Index": file_idx + 1,
                "File_Name": data_files[file_idx] if 0 <= file_idx < len(data_files) else "Unknown",
                var_name: var_val,
                "Value": p["Value"],
                "Step/Error": p["Step/Error"],
                "Pos_Error": p["Pos_Error"],
                "Bound_Low": p["Bound_Low"],
                "Bound_High": p["Bound_High"]
            }
            if base_param_name not in file_groups:
                file_groups[base_param_name] = []
            file_groups[base_param_name].append(file_row)
            
            p["BaseName"] = base_param_name
            p["Variable_Value"] = var_val
            
            # Add ONLY file parameters to the plotter array for Single Histogram fits
            if fittype == 0:
                params_to_plot.append(p)
                
        else:
            # If it misses BOTH regexes above, it lands here.
            global_rows.append(p)
            p["BaseName"] = p["Name"]
            p["Variable_Value"] = "Global"

    if global_rows:
        global_csv_path = "global_parameters.csv"
        with open(global_csv_path, 'w', newline='') as csvfile:
            fieldnames = ["No", "Name", "Value", "Step/Error", "Pos_Error", "Bound_Low", "Bound_High"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in global_rows:
                filtered_row = {k: row[k] for k in fieldnames if k in row}
                writer.writerow(filtered_row)
        print(f">> Exported global fit parameters to '{global_csv_path}'")

    for base_name, rows in file_groups.items():
        file_csv_path = f"file_parameter_{base_name}.csv"
        with open(file_csv_path, 'w', newline='') as csvfile:
            fieldnames = ["File_Index", "File_Name", var_name, "Value", "Step/Error", "Pos_Error", "Bound_Low", "Bound_High"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                filtered_row = {k: row[k] for k in fieldnames if k in row}
                writer.writerow(filtered_row)
        print(f">> Exported file-level parameter tracking sheet to '{file_csv_path}'")

    for base_name, rows in local_groups.items():
        local_csv_path = f"local_parameter_{base_name}.csv"
        with open(local_csv_path, 'w', newline='') as csvfile:
            fieldnames = ["Run_Index", "Detector", "File_Name", var_name, "Value", "Step/Error", "Pos_Error", "Bound_Low", "Bound_High"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                filtered_row = {k: row[k] for k in fieldnames if k in row}
                writer.writerow(filtered_row)
        print(f">> Exported local parameter tracking sheet to '{local_csv_path}'")

    if mapping and params_to_plot:
        plot_parameters_vs_variable(params_to_plot, var_name)

def natural_sort_key(s):
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def resolve_all_timings(data_files, config, raw_file_timings):
    resolved = {}
    cfg_timing = config.get("timing", {})
    detectors = config.get("detectors", {}).values()
    
    defaults = {
        "t0": 1600.0,
        "bkg_range": [20, 1400],
        "data_range": [1600, 100000]
    }

    for det_num in detectors:
        resolved[det_num] = {}
        for i in range(len(data_files)):
            run_idx = i + 1
            resolved[det_num][run_idx] = {}
            
            for key, default_val in defaults.items():
                # 1. Config Priority: Look for config[det][run][key]
                val = cfg_timing.get(str(det_num), {}).get(str(run_idx), {}).get(key)
                
                # 2. ROOT Metadata Priority: Look for raw_meta[det][run][key]
                if val is None:
                    val = raw_file_timings.get(det_num, {}).get(run_idx, {}).get(key)
                
                # 3. Default Priority
                if val is None:
                    val = default_val
                
                resolved[det_num][run_idx][key] = val
    return resolved

def run_orchestration_pipeline(config_file="config.json", output_msr="fit_model.msr", do_plot=False):
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
    
    # -------------------------------------------------------------------------
    # NEW TIMING LOGIC: Pre-resolve all timings before passing to generator
    # -------------------------------------------------------------------------
    print(">> Extracting timing metadata from ROOT files...")
    
    # 1. Fetch raw metadata from ROOT files
    raw_file_timings = build_timing_config(data_files, config.get("detectors", {}))
    
                
    resolved_timings = resolve_all_timings(data_files, config, raw_file_timings)
        
    for custom_cfg in config.get("custom_definitions", []):
        CxxPluginGenerator.generate_and_compile(custom_cfg)
        
    print(f">> Synthesizing MSR script targeting {len(data_files)} ROOT files...")
    generator = MsrGenerator(config, data_files, file_timings=resolved_timings)
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
        dat_files = sorted(glob.glob(f"{base_name}_*.dat"), key=natural_sort_key)
        
        if not dat_files:
            print(f"[!] No ASCII dump files found matching '{base_name}_*.dat'. Ensure musrfit ran successfully.")
        else:
            fittype = config.get("fittype", 2)
            detectors_dict = config.get("detectors", {})
            detector_names = list(detectors_dict.keys())
            num_detectors = len(detector_names) if fittype == 0 else 1
            
            # --- STANDARD PLOTTING (N(t) or standard Asymmetry) ---
            for i, dat_file in enumerate(dat_files):
                pdf_name = dat_file.replace(".dat", ".pdf")
                file_idx = i // num_detectors
                
                det_name = detector_names[i % num_detectors] if fittype == 0 else None
                
                var_val = None
                if file_idx < len(data_files) and mapping:
                    filename = data_files[file_idx]
                    for suffix, s_val in mapping.items():
                        if suffix in filename:
                            var_val = s_val
                            break
                            
                plot_musrfit_data(
                    dat_file, 
                    pdf_name, 
                    variable_name=var_name, 
                    variable_value=var_val, 
                    fittype=fittype, 
                    detector_name=det_name
                )

            # --- NEW: ASYMMETRY RECONSTRUCTION (Single Histogram Mode Only) ---
            if fittype == 0 and num_detectors >= 2:
                print(">> Reconstructing Asymmetry from Single Histogram data...")
                
                # 1. Fallback: Check global parameters for a shared alpha
                global_alpha = 1.0
                if os.path.exists("global_parameters.csv"):
                    try:
                        with open("global_parameters.csv", 'r') as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                if "alpha" in row["Name"].lower():
                                    global_alpha = float(row["Value"])
                                    break
                    except Exception as e:
                        pass

                # 2. Look up Alpha overrides
                alpha_csv = glob.glob("file_parameter_*alpha*.csv") + glob.glob("file_parameter_*Alpha*.csv")
                alphas_by_file = {}
                if alpha_csv:
                    try:
                        with open(alpha_csv[0], 'r') as f:
                            for row in csv.DictReader(f):
                                alphas_by_file[int(row["File_Index"]) - 1] = float(row["Value"])
                    except Exception: pass

                # 3. Look up Background constants AND their errors
                bkg_csvs = glob.glob("local_parameter_*backgr*.csv") + glob.glob("local_parameter_*bkg*.csv")
                bkg_data = {}  # Format: { filename: { "forward": (val, err), "backward": (val, err) } }
                if bkg_csvs:
                    try:
                        with open(bkg_csvs[0], 'r') as f:
                            for row in csv.DictReader(f):
                                fname = row["File_Name"]
                                det = row["Detector"].lower()
                                val = float(row["Value"])
                                
                                # Favor Pos_Error, fallback to Step/Error if MINOS didn't run
                                err = 0.0
                                try:
                                    if row["Pos_Error"].lower() != "none":
                                        err = float(row["Pos_Error"])
                                    else:
                                        err = float(row["Step/Error"])
                                except ValueError:
                                    pass
                                    
                                if fname not in bkg_data: bkg_data[fname] = {}
                                bkg_data[fname][det] = (val, err)
                    except Exception as e:
                        print(f"   [!] Could not parse background values: {e}")

                # 4. Process in pairs
                for file_idx, file_name in enumerate(data_files):
                    f_idx = file_idx * num_detectors
                    b_idx = file_idx * num_detectors + 1
                    
                    if b_idx < len(dat_files):
                        dat_f = dat_files[f_idx]
                        dat_b = dat_files[b_idx]
                        
                        var_val = None
                        if mapping:
                            for suffix, s_val in mapping.items():
                                if suffix in file_name:
                                    var_val = s_val
                                    break
                        
                        alpha_val = alphas_by_file.get(file_idx, global_alpha)
                        
                        # Grab respective backgrounds and errors, defaulting to 0.0 if not found
                        file_bkgs = bkg_data.get(file_name, {})
                        b_f, err_b_f = file_bkgs.get("forward", (0.0, 0.0))
                        b_b, err_b_b = file_bkgs.get("backward", (0.0, 0.0))
                        
                        out_pdf = f"{base_name}_Reconstructed_File{file_idx+1}.pdf"
                        plot_reconstructed_asymmetry(
                            dat_f, dat_b, out_pdf, 
                            alpha=alpha_val, 
                            bkg_f=b_f, bkg_b=b_b,
                            err_bkg_f=err_b_f, err_bkg_b=err_b_b,
                            variable_name=var_name, variable_value=var_val
                        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated muSR Fitting Orchestrator")
    parser.add_argument("-c", "--config", type=str, default="config.json")
    parser.add_argument("-p", "--plot", action="store_true")
    
    args = parser.parse_args()
    run_orchestration_pipeline(config_file=args.config, output_msr="fit_model.msr", do_plot=args.plot)