#!/usr/bin/env python3
import os
import re

def build_timing_config(data_files, detectors_dict):
    """
    Iterates through all run files and builds a nested timing dictionary.
    Structure: { detector_number: { run_index: { timing_data } } }
    
    data_files: list of ROOT file paths.
    detectors_dict: config mapping, e.g., {"forward": 5, "backward": 1}
    """
    timing_config = {}
    
    # Initialize the detector keys based on the config numbers
    for det_name, det_num in detectors_dict.items():
        timing_config[det_num] = {}

    for file_idx, filepath in enumerate(data_files):
        run_idx = file_idx + 1  # 1-based index (Run1, Run2, etc.)
        
        # Extract all detectors from this specific file, keyed by their Histo Number
        file_meta = _extract_single_file(filepath)

        print(f"Extracted metadata for file {filepath}: {file_meta}")  # Debug print
        print(file_meta)
        exit()
        
        for det_name, det_num in detectors_dict.items():
            if not file_meta["success"]:
                # If extraction fails, use safe defaults
                det_data = {}
            else:
                det_data = file_meta["data"].get(det_num, {})
                
            t0 = det_data.get("t0", 1600.0)
            first_good = det_data.get("first_good", 1620)
            last_good = det_data.get("last_good", 102290)
            
            # Populate the run index for this detector
            timing_config[det_num][run_idx] = {
                "t0": t0,
                "bkg_range": [20, int(0.9 * t0)],
                "data_range": [first_good, last_good]
            }
            
    return timing_config

def _extract_single_file(root_file_path):
    """Attempts to extract metadata from a single ROOT file using available backends."""
    try:
        import ROOT
        return _extract_with_root(root_file_path)
    except ImportError:
        pass
    
    try:
        import uproot
        return _extract_with_uproot(root_file_path)
    except ImportError:
        pass
    
    return {"success": False, "error": "Neither uproot nor ROOT library available"}

def _extract_with_root(root_file_path):
    import ROOT
    try:
        f = ROOT.TFile.Open(root_file_path, "READ")
        if not f or f.IsZombie():
            return {"success": False, "error": "Failed to open ROOT file."}
        
        run_header = f.Get("RunHeader")
        if not run_header:
            return {"success": False, "error": "RunHeader not found."}
            
        detector_info = run_header.FindObjectAny("DetectorInfo")
        if not detector_info:
            return {"success": False, "error": "DetectorInfo not found."}

        detectors_data = {}

        for det_array in detector_info:
            det_meta = {}
            for obj in det_array:
                text = f"{obj.GetName()} {obj.GetTitle()}"

                name_match = re.search(r"Name:\s*(\S+)", text)
                num_match  = re.search(r"Histo Number:\s*(\d+)", text)
                t0_match  = re.search(r"Time Zero Bin:\s*([\d\.]+)", text)
                fgb_match = re.search(r"First Good Bin:\s*(\d+)", text)
                lgb_match = re.search(r"Last Good Bin:\s*(\d+)", text)
                
                if name_match: det_meta["Name"] = name_match.group(1)
                if num_match:  det_meta["Number"] = int(num_match.group(1))
                if t0_match:   det_meta["t0"] = float(t0_match.group(1))
                if fgb_match:  det_meta["first_good"] = int(fgb_match.group(1))
                if lgb_match:  det_meta["last_good"] = int(lgb_match.group(1))

            # Store the detector using its Histo Number as the dictionary key
            if "Number" in det_meta:
                detectors_data[det_meta["Number"]] = det_meta

        f.Close()
        return {"success": True, "data": detectors_data}

    except Exception as e:
        return {"success": False, "error": f"PyROOT error: {str(e)}"}

def _extract_with_uproot(root_file_path):
    import uproot
    try:
        with uproot.open(root_file_path) as file:
            det_info_key = [k for k in file.keys() if "DetectorInfo" in k]
            if not det_info_key:
                return {"success": False, "error": "DetectorInfo path not found"}
            
            detector_info = file[det_info_key[0]]
            detectors_data = {}

            for det_key in detector_info.keys():
                det_array = detector_info[det_key]
                det_meta = {}
                
                for member in getattr(det_array, "members", []):
                    text = str(member)
                    
                    name_match = re.search(r"Name:\s*(\S+)", text)
                    num_match  = re.search(r"Histo Number:\s*(\d+)", text)
                    t0_match  = re.search(r"Time Zero Bin:\s*([\d\.]+)", text)
                    fgb_match = re.search(r"First Good Bin:\s*(\d+)", text)
                    lgb_match = re.search(r"Last Good Bin:\s*(\d+)", text)
                    
                    if name_match: det_meta["Name"] = name_match.group(1)
                    if num_match:  det_meta["Number"] = int(num_match.group(1))
                    if t0_match:   det_meta["t0"] = float(t0_match.group(1))
                    if fgb_match:  det_meta["first_good"] = int(fgb_match.group(1))
                    if lgb_match:  det_meta["last_good"] = int(lgb_match.group(1))

                # Store the detector using its Histo Number as the dictionary key
                if "Number" in det_meta:
                    detectors_data[det_meta["Number"]] = det_meta

            return {"success": True, "data": detectors_data}
    except Exception as e:
        return {"success": False, "error": f"Uproot error: {str(e)}"}