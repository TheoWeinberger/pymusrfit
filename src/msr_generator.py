# msr_generator.py
class MsrGenerator:
    """Manages string assembly formatting, variable registration, and non-positional parameter tracking."""
    def __init__(self, config_dict, data_files, file_timings=None):
        self.config = config_dict
        self.data_files = data_files
        self.file_timings = file_timings or {}
        self.msr_lines = []
        
        self.alpha_param_num = None
        self.asym_base_name = ""
        self.asym_registry = {}    # Format: { "global" or det_name: fit_index }
        self.global_registry = {}  # Format: { "variable_name": fit_index }
        self.file_registry = {}    # Format: { "variable_name": [file1_idx, file2_idx, ...] }
        self.local_registry = {}   # Format: { "variable_name": [run1_idx, run2_idx, ...] }
        self.map_token_sequence = []
        self.param_counter = 1

    def build_parameters(self):
        self.msr_lines.append("FITPARAMETER")
        self.msr_lines.append("#      Nr. Name                        Value     Step      Pos_Error  Boundaries")
        
        # 1. Scale instrument tracking attributes
        alpha_cfg = self.config.get("alpha", {"value": 1.0, "step": 0.0, "fit": False})
        step = alpha_cfg["step"] if alpha_cfg.get("fit", False) else 0.0
        pos_err = alpha_cfg.get("pos_err", "none")
        boundaries = " ".join(str(b) for b in alpha_cfg.get("boundaries", []))
        self.msr_lines.append(f"        {self.param_counter} alpha                       {alpha_cfg['value']}      {step}       {pos_err}        {boundaries}")
        self.alpha_param_num = self.param_counter
        self.param_counter += 1
        
        fittype = self.config.get("fittype", 2)
        detectors_dict = self.config.get("detectors", {})
        separator_line = "#" * 63
        
        # 2. Process Asymmetry Parameters Specially
        asym_cfg = self.config.get("asymmetry", {})
        self.asym_base_name = asym_cfg.get("name", "Asym")
        
        if fittype == 2:
            # Single global asymmetry for fittype 2
            val = asym_cfg.get("value", 0.0)
            step = asym_cfg.get("step", 0.0)
            pos_err = asym_cfg.get("pos_err", "none")
            boundaries = " ".join(str(b) for b in asym_cfg.get("boundaries", []))
            self.msr_lines.append(f"        {self.param_counter} {self.asym_base_name:27} {val} {step}       {pos_err}        {boundaries}")
            self.asym_registry["global"] = self.param_counter
            self.param_counter += 1
            
        elif fittype == 0:
            # Detector-specific asymmetry constants for fittype 0
            for det_name, det_val in detectors_dict.items():
                # Allow fallback checking stringified detector number ("1") or name ("forward")
                det_asym = asym_cfg.get(str(det_val), asym_cfg.get(det_name, {}))
                val = det_asym.get("value", asym_cfg.get("value", 0.0))
                step = det_asym.get("step", asym_cfg.get("step", 0.0))
                pos_err = det_asym.get("pos_err", asym_cfg.get("pos_err", "none"))
                boundaries = " ".join(str(b) for b in det_asym.get("boundaries", asym_cfg.get("boundaries", [])))
                
                param_name = f"{self.asym_base_name}_{det_name}"
                self.msr_lines.append(f"        {self.param_counter} {param_name:27} {val} {step}       {pos_err}        {boundaries}")
                self.asym_registry[det_name] = self.param_counter
                self.param_counter += 1
        
        # 3. Load and register remaining Global elements
        for p in self.config.get("global_params", []):
            if p["name"] == self.asym_base_name: continue # Ignore if accidentally left in global_params
            pos_err = p.get("pos_err", "none")
            boundaries = " ".join(str(b) for b in p.get("boundaries", []))
            self.msr_lines.append(f"        {self.param_counter} {p['name']:27} {p['value']} {p['step']}       {pos_err}        {boundaries}")
            self.global_registry[p['name']] = self.param_counter
            self.param_counter += 1
            
        # 4. Allocate and register File-level elements
        for p in self.config.get("file_params", []):
            self.file_registry[p['name']] = []
            
        for i, file in enumerate(self.data_files):
            for p in self.config.get("file_params", []):
                pos_err = p.get("pos_err", "none")
                boundaries = " ".join(str(b) for b in p.get("boundaries", []))
                self.msr_lines.append(f"        {self.param_counter} {p['name']}_File_{i+1:21} {p['value']} {p['step']}       {pos_err}        {boundaries}")
                self.file_registry[p['name']].append(self.param_counter)
                self.param_counter += 1

        # 5. Allocate references for individual Local instances
        for p in self.config.get("local_params", []):
            self.local_registry[p['name']] = []
            
        if fittype == 2:
            # Traditional flat index per run file for asymmetry fitting
            for i, file in enumerate(self.data_files):
                self.msr_lines.append(separator_line)
                self.msr_lines.append(f"# Run {i+1} local parameters")
                
                for p in self.config.get("local_params", []):
                    pos_err = p.get("pos_err", "none")
                    boundaries = " ".join(str(b) for b in p.get("boundaries", []))
                    param_name = f"{p['name']}_Run{i+1}"
                    self.msr_lines.append(f"        {self.param_counter} {param_name:27} {p['value']} {p['step']}       {pos_err}        {boundaries}")
                    self.local_registry[p['name']].append(self.param_counter)
                    self.param_counter += 1
                    
        elif fittype == 0:
            # Expanded name architecture tracking both Run Number and Detector channel
            for i, file in enumerate(self.data_files):
                self.msr_lines.append(separator_line)
                self.msr_lines.append(f"# Run {i+1} local parameters")
                
                for det_name, det_val in detectors_dict.items():
                    for p in self.config.get("local_params", []):
                        pos_err = p.get("pos_err", "none")
                        boundaries = " ".join(str(b) for b in p.get("boundaries", []))
                        
                        param_name = f"{p['name']}_Run{i+1}_{det_name}"
                        self.msr_lines.append(f"        {self.param_counter} {param_name:27} {p['value']} {p['step']}       {pos_err}        {boundaries}")
                        self.local_registry[p['name']].append(self.param_counter)
                        self.param_counter += 1
                        
        self.msr_lines.append("")

    def build_theory(self):
        self.msr_lines.append("THEORY")
        custom_names = {cf["name"] for cf in self.config.get("custom_definitions", [])}
        map_counter = 1
        
        for line in self.config.get("theory_block", []):
            parts = line.split()
            if not parts: continue
            func_name = parts[0]
            param_tokens = parts[1:]
            
            line_maps = []
            for token in param_tokens:
                self.map_token_sequence.append(token)
                line_maps.append(f"map{map_counter}")
                map_counter += 1
                
            if func_name in custom_names:
                self.msr_lines.append(f"userFcn  plugins/lib{func_name}Library  {func_name}  " + " ".join(line_maps))
            else:
                self.msr_lines.append(f"{func_name}      " + " ".join(line_maps))
        self.msr_lines.append("")

    def build_runs(self):
        run_format = self.config.get("instrument", {}).get("format", "MUD")
        facility = self.config.get("instrument", {}).get("facility", "TRIUMF (WISH)")
        
        fittype = self.config.get("fittype", 2)
        detectors_dict = self.config.get("detectors", {})
        current_run_idx = 0
        
        for i, file in enumerate(self.data_files):
            time_cfg = self.file_timings.get(file, self.config.get("timing", {}))
            
            if not time_cfg:
                time_cfg = {
                    "bkg_range": [320, 1440],
                    "data_range": [1600, 160000],
                    "t0": 1600
                }
            
            if fittype == 2:
                # Standard Asymmetry Fit Block
                fwd = detectors_dict.get("forward", 1)
                bwd = detectors_dict.get("backward", 2)
                
                self.msr_lines.append(f"RUN {file} {facility} {run_format} (name beamline institute data-file-format)")
                self.msr_lines.append("fittype         2         (asymmetry fit)")
                self.msr_lines.append(f"alpha           {self.alpha_param_num}")
                
                map_indices = []
                for var_name in self.map_token_sequence:
                    if var_name == self.asym_base_name:
                        map_indices.append(str(self.asym_registry["global"]))
                    elif var_name in self.local_registry:
                        map_indices.append(str(self.local_registry[var_name][current_run_idx]))
                    elif var_name in self.file_registry:
                        map_indices.append(str(self.file_registry[var_name][i]))
                    elif var_name in self.global_registry:
                        map_indices.append(str(self.global_registry[var_name]))
                    else:
                        raise KeyError(f"Configuration Reference Mismatch: '{var_name}' is unmapped.")
                        
                self.msr_lines.append("map             " + " ".join(map_indices))
                self.msr_lines.append(f"forward         {fwd}")
                self.msr_lines.append(f"backward        {bwd}")
                
                b_f_start, b_f_end = time_cfg.get('bkg_range_forward', time_cfg.get('bkg_range', [0,0]))
                b_b_start, b_b_end = time_cfg.get('bkg_range_backward', time_cfg.get('bkg_range', [0,0]))
                d_f_start, d_f_end = time_cfg.get('data_range_forward', time_cfg.get('data_range', [0,0]))
                d_b_start, d_b_end = time_cfg.get('data_range_backward', time_cfg.get('data_range', [0,0]))
                t0_f, t0_b = time_cfg.get('t0_forward', time_cfg.get('t0', 0)), time_cfg.get('t0_backward', time_cfg.get('t0', 0))
                
                self.msr_lines.append(f"background      {b_f_start}      {b_f_end}     {b_b_start}      {b_b_end}")
                self.msr_lines.append(f"data            {d_f_start}    {d_f_end}  {d_b_start}    {d_b_end}")
                self.msr_lines.append(f"t0              {t0_f}  {t0_b}")
                
                fit_range = self.config.get('fit_params', {}).get("fit_range", [0, 8])
                packing = self.config.get('fit_params', {}).get("packing", 100)
                self.msr_lines.append(f"fit             {fit_range[0]}       {fit_range[1]}")
                self.msr_lines.append(f"packing         {packing}")
                self.msr_lines.append("")
                current_run_idx += 1
                
            elif fittype == 0:
                # Single Histogram Fit Block
                for det_name, det_val in detectors_dict.items():
                    self.msr_lines.append(f"RUN {file} {facility} {run_format} (name beamline institute data-file-format)")
                    self.msr_lines.append("fittype         0         (single histogram fit)")
                    
                    if "norm" in self.local_registry:
                        norm_param_num = self.local_registry["norm"][current_run_idx]
                        self.msr_lines.append(f"norm            {norm_param_num}")
                    else:
                        raise KeyError("Missing required local parameter 'norm' for fittype 0.")
                        
                    if "backgr" in self.local_registry:
                        backgr_param_num = self.local_registry["backgr"][current_run_idx]
                        self.msr_lines.append(f"backgr.fit      {backgr_param_num}")
                    else:
                        raise KeyError("Missing required local parameter 'backgr' for fittype 0.")
                    
                    map_indices = []
                    for var_name in self.map_token_sequence:
                        if var_name == self.asym_base_name:
                            map_indices.append(str(self.asym_registry[det_name]))
                        elif var_name in self.local_registry:
                            map_indices.append(str(self.local_registry[var_name][current_run_idx]))
                        elif var_name in self.file_registry:
                            map_indices.append(str(self.file_registry[var_name][i]))
                        elif var_name in self.global_registry:
                            map_indices.append(str(self.global_registry[var_name]))
                        else:
                            raise KeyError(f"Configuration Reference Mismatch: '{var_name}' is unmapped.")
                            
                    self.msr_lines.append("map             " + " ".join(map_indices))
                    self.msr_lines.append(f"forward         {det_val}")
                    
                    data_start, data_end = time_cfg.get(f'data_range_{det_name}', time_cfg.get('data_range', [0,0]))
                    t0_val = time_cfg.get(f't0_{det_name}', time_cfg.get('t0', 0))
                    
                    self.msr_lines.append(f"data            {data_start}    {data_end}")
                    self.msr_lines.append(f"t0              {t0_val}")
                    
                    fit_range = self.config.get('fit_params', {}).get("fit_range", [0, 8])
                    packing = self.config.get('fit_params', {}).get("packing", 100)
                    self.msr_lines.append(f"fit             {fit_range[0]}       {fit_range[1]}")
                    self.msr_lines.append(f"packing         {packing}")
                    self.msr_lines.append("")
                    current_run_idx += 1
                    
        self.total_run_count = current_run_idx

    def build_footer(self):
        self.msr_lines.append("COMMANDS")
        if self.config.get("fittype", 2) == 0:
            self.msr_lines.append("SCALE_N0_BKG TRUE")
        self.msr_lines.append("MINIMIZE")
        self.msr_lines.append("MINOS")
        self.msr_lines.append("#HESSE")
        self.msr_lines.append("SAVE")
        self.msr_lines.append("")

    def build_fourier(self):
        fourier_config = self.config.get("fourier", {})
        if not fourier_config: return
        self.msr_lines.append("FOURIER")
        self.msr_lines.append(f"units            {fourier_config.get('units', 'Gauss')}   # units either 'Gauss', 'Tesla', 'MHz', or 'Mc/s'")
        self.msr_lines.append(f"fourier_power    {fourier_config.get('power', 12)}")
        self.msr_lines.append(f"apodization      {fourier_config.get('apodization', 'NONE')}    # NONE, WEAK, MEDIUM, STRONG")
        self.msr_lines.append(f"plot             {fourier_config.get('plot', 'POWER')}   # REAL, IMAG, REAL_AND_IMAG, POWER, PHASE, PHASE_OPT_REAL")
        self.msr_lines.append(f"phase            {fourier_config.get('phase', 8)}")
        self.msr_lines.append(f"range            {fourier_config.get('range', [0, 200])[0]}    {fourier_config.get('range', [0, 200])[1]}")
        self.msr_lines.append("")

    def build_plot(self):
        plot_config = self.config.get("plot", {})
        fittype = self.config.get("fittype", 2)
        
        if getattr(self, 'total_run_count', 0) > 0:
            run_sequence = " ".join(str(r) for r in range(1, self.total_run_count + 1))
        else:
            run_sequence = plot_config.get('runs', '1')
            
        if fittype == 0:
            self.msr_lines.append("PLOT 0   (single histo plot)")
            self.msr_lines.append("lifetimecorrection")
            self.msr_lines.append(f"runs     {run_sequence}")
            rng = plot_config.get("range", [0, 9, -0.3, 0.3])
            self.msr_lines.append(f"range    {rng[0]}   {rng[1]}   {rng[2]}   {rng[3]}")
            self.msr_lines.append("")
        else:
            self.msr_lines.append("PLOT 2   (asymmetry plot)")
            self.msr_lines.append(f"runs     {run_sequence}")
            rng = plot_config.get("range", [0, 8, 0, 0.25])
            self.msr_lines.append(f"range    {rng[0]}   {rng[1]}   {rng[2]}   {rng[3]}")
            self.msr_lines.append("")

    def build_statistic(self):
        from datetime import datetime
        stat_config = self.config.get("statistic", {})
        
        timestamp = stat_config.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        chisq = stat_config.get("chisq", 0.0)
        ndf = stat_config.get("ndf", 0)
        
        self.msr_lines.append(f"STATISTIC --- {timestamp}")
        if isinstance(chisq, (int, float)) and isinstance(ndf, (int, float)) and ndf != 0:
            chisq_ndf = float(chisq) / float(ndf)
            self.msr_lines.append(f"  chisq = {chisq}, NDF = {ndf}, chisq/NDF = {chisq_ndf:.6f}")
        else:
            self.msr_lines.append(f"  chisq = {chisq}, NDF = {ndf}, chisq/NDF = 0.000000")
        self.msr_lines.append("")

    def generate_msr_string(self):
        separator = "#" * 63
        
        self.msr_lines.append(self.config["title"])
        self.msr_lines.append(separator)
        
        self.build_parameters()
        self.msr_lines.append(separator)
        
        self.build_theory()
        self.msr_lines.append(separator)
        
        self.build_runs()
        self.msr_lines.append(separator)
        
        self.build_footer()
        self.msr_lines.append(separator)
        
        self.build_fourier()
        self.msr_lines.append(separator)
        
        self.build_plot()
        self.msr_lines.append(separator)
        
        self.build_statistic()
        
        return "\n".join(self.msr_lines)