# plot_musr.py
import os
import re

def plot_musrfit_data(dat_filepath, output_image, variable_name=None, variable_value=None):
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
        
        plt.plot(time, theory, '-', color='red', linewidth=2, label='Theory Fit', zorder = 10)
        
        plt.xlabel(r'Time ($\mu s$)', fontsize=10)
        plt.ylabel('Asymmetry', fontsize=10)
        
        # Ingest suffix mapping variables into the title if available
        title_text = f'muSR Asymmetry Fit ({os.path.basename(dat_filepath)})'
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


def plot_parameters_vs_variable(params, var_name):
    """Generates physical dependency plots for each distinct local fit parameter as a function of the external variable."""
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
        # Sort points by the independent physical variable values
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Standalone plotter for musrfit ASCII dump files (.dat)")
    parser.add_argument("filename", help="Path to the musrfit .dat file")
    parser.add_argument("-o", "--output", help="Output image filename (e.g., plot.pdf)", default=None)
    
    args = parser.parse_args()
    out_img = args.output if args.output else args.filename.replace(".dat", ".pdf")
    plot_musrfit_data(args.filename, out_img)