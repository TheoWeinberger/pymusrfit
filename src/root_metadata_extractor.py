#!/usr/bin/env python3
import os
import re

def extract_root_metadata(root_file_path, forward_name="Forw", backward_name="Back"):
    """
    Extracts explicit timing metadata from the TObjArray/TObjString structure 
    found inside RunHeader/DetectorInfo.
    """
    try:
        import ROOT
        return _extract_with_root(root_file_path, forward_name, backward_name)
    except ImportError:
        pass
    
    try:
        import uproot
        return _extract_with_uproot(root_file_path, forward_name, backward_name)
    except ImportError:
        pass
    
    return {"success": False, "error": "Neither uproot nor ROOT library available"}

def _extract_with_root(root_file_path, forward_name, backward_name):
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

                # FIX 1: \S+ captures everything up to the next space, preserving hyphens
                name_match = re.search(r"Name:\s*(\S+)", text)
                
                # FIX 2: Capture the Histo Number
                num_match  = re.search(r"Histo Number:\s*(\d+)", text)
                
                t0_match  = re.search(r"Time Zero Bin:\s*([\d\.]+)", text)
                fgb_match = re.search(r"First Good Bin:\s*(\d+)", text)
                lgb_match = re.search(r"Last Good Bin:\s*(\d+)", text)
                len_match = re.search(r"Histo Length:\s*(\d+)", text)
                
                if name_match: det_meta["Name"] = name_match.group(1)
                if num_match:  det_meta["Number"] = int(num_match.group(1))
                if t0_match:   det_meta["t0"] = float(t0_match.group(1))
                if fgb_match:  det_meta["first_good"] = int(fgb_match.group(1))
                if lgb_match:  det_meta["last_good"] = int(lgb_match.group(1))
                if len_match:  det_meta["length"] = int(len_match.group(1))

            if "Name" in det_meta:
                # Storing using the Name as the key so _build_response_dict doesn't break
                detectors_data[det_meta["Name"]] = det_meta

        f.Close()
        print(_build_response_dict(detectors_data, forward_name, backward_name))
        exit()
        return _build_response_dict(detectors_data, forward_name, backward_name)

    except Exception as e:
        return {"success": False, "error": f"PyROOT error: {str(e)}"}

def _extract_with_uproot(root_file_path, forward_name, backward_name):
    import uproot
    try:
        with uproot.open(root_file_path) as file:
            det_info_key = [k for k in file.keys() if "DetectorInfo" in k]
            if not det_info_key:
                return {"success": False, "error": "DetectorInfo path not found via uproot"}
            
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
                    len_match = re.search(r"Histo Length:\s*(\d+)", text)
                    
                    if name_match: det_meta["Name"] = name_match.group(1)
                    if num_match:  det_meta["Number"] = int(num_match.group(1))
                    if t0_match:   det_meta["t0"] = float(t0_match.group(1))
                    if fgb_match:  det_meta["first_good"] = int(fgb_match.group(1))
                    if lgb_match:  det_meta["last_good"] = int(lgb_match.group(1))
                    if len_match:  det_meta["length"] = int(len_match.group(1))

                if "Name" in det_meta:
                    detectors_data[det_meta["Name"]] = det_meta

            return _build_response_dict(detectors_data, forward_name, backward_name)
    except Exception as e:
        return {"success": False, "error": f"Uproot error: {str(e)}"}

def _build_response_dict(detectors_data, forward_name, backward_name):
    f_det = detectors_data.get(forward_name, {})
    b_det = detectors_data.get(backward_name, {})
    
    t0_f = f_det.get("first_good", 1600) 
    t0_b = b_det.get("first_good", 1600)
    
    return {
        "t0_forward": t0_f,
        "t0_backward": t0_b,
        "data_range_forward": [f_det.get("first_good"), f_det.get("last_good")],
        "data_range_backward": [b_det.get("first_good"), b_det.get("last_good")],
        "bkg_range_forward": [20, int(0.9 * t0_f)], 
        "bkg_range_backward": [20, int(0.9 * t0_b)], 
        "success": True if f_det or b_det else False
    }