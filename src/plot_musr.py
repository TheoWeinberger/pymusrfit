# plot_musr.py
import os
import re

def plot_musrfit_data(dat_filepath, output_image, variable_name=None, variable_value=None, fittype=2, detector_name=None):
    """Parses a musrfit ASCII dump file and generates a plot, optionally including an experimental variable header."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("[!] Error: matplotlib and numpy are required for plotting. Install them via pip.")
        return

    try:
        data = np.loadtxt(dat_filepath, delimiter=',', comments='%')
        if data.size == 0:
            print(f"[!] Empty data in {dat_filepath}")
            return
            
        time = data[:, 0]
        value = data[:, 1]
        error = data[:, 2]
        theory = data[:, 3]
        
        plt.figure(figsize=(6, 6))

        plt.tick_params('both', which='major', direction='in', length=5, width=1.2,
                   bottom=True, top=True, left=True, right=True)

        plt.tick_params('both', which='minor', direction='in', length=3, width=1,
                   bottom=True, top=True, left=True, right=True)
        
        plt.errorbar(time, value, yerr=error, fmt='o', markersize=3, 
                     color='black', alpha=0.5, label='Data', elinewidth=1)
        
        plt.plot(time, theory, '-', color='red', linewidth=2, label='Theory Fit')
        
        plt.xlabel(r'Time ($\mu s$)', fontsize=10)
        
        # --- DYNAMIC Y-AXIS LABEL ---
        y_label = 'N(t)' if fittype == 0 else 'Asymmetry'
        plt.ylabel(y_label, fontsize=10)
        
        # --- DYNAMIC TITLE INJECTION ---
        title_text = f'muSR Fit ({os.path.basename(dat_filepath)})'
        if fittype == 0 and detector_name:
            title_text += f' | Detector: {detector_name.capitalize()}'
            
        if variable_name and variable_value is not None:
            title_text += f'\n{variable_name}: {variable_value}'
            
        plt.title(title_text, fontsize=10)
        plt.legend(fontsize=10, frameon=False)
        plt.tight_layout()
        
        plt.savefig(output_image, dpi=150)
        plt.close()
        print(f"   -> Saved plot to '{output_image}'")
    except Exception as e:
        print(f"[!] Failed to plot {dat_filepath}: {e}")


def plot_reconstructed_asymmetry(dat_f, dat_b, output_image, alpha=1.0, bkg_f=0.0, bkg_b=0.0, err_bkg_f=0.0, err_bkg_b=0.0, variable_name=None, variable_value=None):
    """Calculates, plots, and exports the combined Asymmetry from two Single Histogram .dat files using a stabilized theoretical denominator."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("[!] Error: matplotlib and numpy are required for plotting.")
        return

    try:
        # Load Forward Data
        data_f = np.loadtxt(dat_f, delimiter=',', comments='%')
        time_us = data_f[:, 0]
        N_f_raw = data_f[:, 1]
        sigma_N_f = data_f[:, 2]
        theory_f_raw = data_f[:, 3]

        # Load Backward Data
        data_b = np.loadtxt(dat_b, delimiter=',', comments='%')
        N_b_raw = data_b[:, 1]
        sigma_N_b = data_b[:, 2]
        theory_b_raw = data_b[:, 3]

        # --- SUBTRACT BACKGROUND ---
        N_f = N_f_raw - bkg_f
        N_b = N_b_raw - bkg_b
        theory_f = theory_f_raw - bkg_f
        theory_b = theory_b_raw - bkg_b

        # --- THEORETICAL DENOMINATOR (Stabilization) ---
        theory_denom = theory_f + (alpha * theory_b)
        valid = theory_denom != 0
        
        asymmetry = np.full_like(N_f, np.nan, dtype=float)
        asymmetry_error = np.full_like(N_f, np.nan, dtype=float)
        theory_asym = np.full_like(N_f, np.nan, dtype=float)
        
        # 1. Calculate Experimental Asymmetry (Stabilized)
        asymmetry[valid] = (N_f[valid] - (alpha * N_b[valid])) / theory_denom[valid]
        
        # 2. Error propagation (Stabilized)
        variance_sum = (sigma_N_f[valid] ** 2) + ((alpha ** 2) * (sigma_N_b[valid] ** 2))
        asymmetry_error[valid] = np.sqrt(variance_sum) / np.abs(theory_denom[valid])
        
        # 3. Calculate Theory Asymmetry
        theory_asym[valid] = (theory_f[valid] - (alpha * theory_b[valid])) / theory_denom[valid]

        # --- EXPORT TO .DAT FILE ---
        output_dat = output_image.replace('.pdf', '.dat')
        valid_count = np.sum(valid)
        
        with open(output_dat, 'w') as f:
            f.write(f"% number of data values = {valid_count}\n")
            f.write("% time (us), value, error, theory\n")
            for t, v, e, th in zip(time_us[valid], asymmetry[valid], asymmetry_error[valid], theory_asym[valid]):
                th_val = th if not np.isnan(th) else 0.0
                f.write(f"{t:.5f}, {v:.6f}, {e:.6f}, {th_val:.6f}\n")
                
        print(f"   -> Saved reconstructed data array to '{output_dat}'")

        # --- PLOTTING ---
        fig, ax = plt.subplots(figsize=(6, 6))
        
        ax.tick_params('both', which='major', direction='in', length=5, width=1.2, bottom=True, top=True, left=True, right=True)
        ax.tick_params('both', which='minor', direction='in', length=3, width=1, bottom=True, top=True, left=True, right=True)
        
        valid_mask = ~np.isnan(asymmetry)
        
        ax.errorbar(time_us[valid_mask], asymmetry[valid_mask], yerr=asymmetry_error[valid_mask], 
                    fmt='o', markersize=3, color='black', alpha=0.5, label='Reconstructed Data', elinewidth=1)
                    
        # FIX: Changed `valid_theory` to just `valid` here!
        ax.plot(time_us[valid], theory_asym[valid], '-', color='red', linewidth=2, label='Reconstructed Theory')
        
        ax.axhline(0, color='blue', linestyle='--', linewidth=1, alpha=0.5, label='A = 0')
        
        ax.set_xlabel(r'Time ($\mu s$)', fontsize=10)
        ax.set_ylabel(r'Asymmetry $A(t)$', fontsize=10)
        
        title_text = f'Reconstructed Asymmetry (alpha={alpha:.3f})'
        if variable_name and variable_value is not None:
            title_text += f'\n{variable_name}: {variable_value}'
            
        ax.set_title(title_text, fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=10, frameon=False)
        
        plt.tight_layout()
        plt.savefig(output_image, dpi=150)
        plt.close()
        
        print(f"   -> Saved reconstructed asymmetry plot to '{output_image}'")
        
    except Exception as e:
        print(f"[!] Failed to reconstruct asymmetry for {dat_f} / {dat_b}: {e}")


def plot_parameters_vs_variable(params, var_name):
    """Generates physical dependency plots for each distinct fit parameter as a function of the external variable."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return

    local_groups = {}
    for p in params:
        v_val = p.get("Variable_Value", "Global")
        if v_val not in ["Global", "Unknown"]:
            base = p.get("BaseName", p["Name"])
            try:
                val_float = float(p["Value"])
                err_float = float(p["Pos_Error"])
                var_float = float(v_val)
                if base not in local_groups:
                    local_groups[base] = []
                local_groups[base].append((var_float, val_float, err_float))
            except ValueError:
                continue
                
    if not local_groups:
        return

    print(f">> Generating parameter trend plots vs {var_name}...")
    for base, points in local_groups.items():
        points = sorted(points, key=lambda x: x[0])
        x_vals = [pt[0] for pt in points]
        y_vals = [pt[1] for pt in points]
        y_errs = [pt[2] for pt in points]
        
        plt.figure(figsize=(6, 5))
        plt.errorbar(x_vals, y_vals, yerr=y_errs, fmt='o-', color='blue', linewidth=2, capsize=4, label='Fit Result')
        plt.xlabel(var_name, fontsize=10)
        plt.ylabel(f"Solved Value ({base})", fontsize=10)
        plt.title(f"Parameter Dependency: {base} vs {var_name}", fontsize=10)

        plt.tick_params('both', which='major', direction='in', length=5, width=1.2,
                   bottom=True, top=True, left=True, right=True)

        plt.tick_params('both', which='minor', direction='in', length=3, width=1,
                   bottom=True, top=True, left=True, right=True)
        
        plt.legend(fontsize=10, frameon=False)
        plt.tight_layout()
        
        clean_var_name = re.sub(r'[^\w\-_\. ]', '_', var_name).replace(' ', '_')
        output_image = f"dependency_{base}_vs_{clean_var_name}.pdf"
        plt.savefig(output_image, dpi=150)
        plt.close()
        print(f"   -> Saved physical dependency plot to '{output_image}'")