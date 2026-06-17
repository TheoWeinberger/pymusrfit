#!/usr/bin/env python3
import os
import re

def extract_root_metadata(root_file_path, forward_name="Forw", backward_name="Back"):
    """
    Extracts explicit timing metadata from the TObjArray/TObjString structure 
    found inside RunHeader/DetectorInfo.
    """
    # Try PyROOT first (highly reliable for custom C++ collections like TObjArray)
    try:
        import ROOT
        print("hi")
        exit()
        return _extract_with_root(root_file_path, forward_name, backward_name)
    except ImportError:
        print("hi")
        exit()
        pass
    
    # Fallback to Uproot
    try:
        import uproot
        return _extract_with_uproot(root_file_path, forward_name, backward_name)
    except ImportError:
        print("hi")
        exit()
        pass
    
    return {
        "success": False,
        "error": "Neither uproot nor ROOT library available"
    }

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

        # Loop through each Detector TObjArray (Detector001, Detector002, etc.)
        for det_array in detector_info:
            det_meta = {}
            # Loop through the TObjString elements inside the array
            for obj in det_array:
                # Combine Name and Title to catch all text formats safely
                text = f"{obj.GetName()} {obj.GetTitle()}"

                print(text)
                exit()
                
                # Extract key metadata pairs using regex
                name_match = re.search(r"Name:\s*([^\s\-]+)", text)
                t0_match = re.search(r"Time Zero Bin:\s*([\d\.]+)", text)
                fgb_match = re.search(r"First Good Bin:\s*(\d+)", text)
                lgb_match = re.search(r"Last Good Bin:\s*(\d+)", text)
                len_match = re.search(r"Histo Length:\s*(\d+)", text)
                
                if name_match: det_meta["Name"] = name_match.group(1)
                if t0_match:   det_meta["t0"] = float(t0_match.group(1))
                if fgb_match:  det_meta["first_good"] = int(fgb_match.group(1))
                if lgb_match:  det_meta["last_good"] = int(lgb_match.group(1))
                if len_match:  det_meta["length"] = int(len_match.group(1))

            if "Name" in det_meta:
                detectors_data[det_meta["Name"]] = det_meta

        f.Close()
        return _build_response_dict(detectors_data, forward_name, backward_name)

    except Exception as e:
        return {"success": False, "error": f"PyROOT error: {str(e)}"}

def _extract_with_uproot(root_file_path, forward_name, backward_name):
    import uproot
    try:
        with uproot.open(root_file_path) as file:
            # Locate DetectorInfo folder
            det_info_key = [k for k in file.keys() if "DetectorInfo" in k]
            if not det_info_key:
                return {"success": False, "error": "DetectorInfo path not found via uproot"}
            
            detector_info = file[det_info_key[0]]
            detectors_data = {}

            # Uproot reads nested TObjArrays as class instances with members
            for det_key in detector_info.keys():
                det_array = detector_info[det_key]
                det_meta = {}
                
                # Handle uproot string listings inside object members safely
                for member in getattr(det_array, "members", []):
                    text = str(member)
                    
                    name_match = re.search(r"Name:\s*([^\s\-]+)", text)
                    t0_match = re.search(r"Time Zero Bin:\s*([\d\.]+)", text)
                    fgb_match = re.search(r"First Good Bin:\s*(\d+)", text)
                    lgb_match = re.search(r"Last Good Bin:\s*(\d+)", text)
                    len_match = re.search(r"Histo Length:\s*(\d+)", text)
                    
                    if name_match: det_meta["Name"] = name_match.group(1)
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
    """Helper to structure compiled metadata into your target output format."""
    f_det = detectors_data.get(forward_name, {})
    b_det = detectors_data.get(backward_name, {})
    
    # Use 'First Good Bin' if you want data boundaries, or 't0' if you want exact zero-point
    t0_f = f_det.get("first_good", 1600) 
    t0_b = b_det.get("first_good", 1600)
    data_length = f_det.get("length", 102400)
    
    return {
        "t0_forward": t0_f,
        "t0_backward": t0_b,
        "data_range_forward": [f_det.get("first_good"), f_det.get("last_good")],
        "data_range_backward": [b_det.get("first_good"), b_det.get("last_good")],
        "bkg_range_forward": [20, int(0.9 * t0_f)],  # Default to 20% to 90% of t0 for background
        "bkg_range_backward": [20, int(0.9 * t0_b)],  # Default to 20% to 90% of t0 for background
        "success": True if f_det or b_det else False
    }
