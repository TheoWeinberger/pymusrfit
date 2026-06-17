# cxx_plugin_generator.py
import os
import subprocess
import sympy as sp
from sympy.parsing.sympy_parser import parse_expr

class CxxPluginGenerator:
    """Handles transpilation of math functions and orchestrates builds within a dedicated subdirectory."""
    
    @staticmethod
    def generate_and_compile(custom_cfg, output_dir="plugins"):
        plugin_name = custom_cfg["name"]
        library_name = f"{plugin_name}Library"
        python_math = custom_cfg["equation"]
        param_names = custom_cfg["parameters"]

        print(f">> Synthesizing C++ Source Layer for: {plugin_name}")
        print(f"   -> Isolating building tree inside subdirectory: './{output_dir}/'")
        
        # Ensure the clean subdirectory target directory path exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Parse expression tree safely via SymPy
        local_dict = {name: sp.Symbol(name) for name in param_names + ['t']}
        expr = parse_expr(python_math, local_dict=local_dict)
        mapping = {sp.Symbol(name): sp.Symbol(f"param[{i}]") for i, name in enumerate(param_names)}
        cpp_math = sp.ccode(expr.subs(mapping))
        
        # 1. Class Interface Header (.h)
        h_code = f"""#ifndef _{plugin_name.upper()}_H_
#define _{plugin_name.upper()}_H_

#include <vector>
#include "PUserFcnBase.h"

class {plugin_name} : public PUserFcnBase {{
  public:
    {plugin_name}() {{}}
    virtual ~{plugin_name}() {{}}

    Bool_t NeedGlobalPart() const override {{ return false; }}
    void SetGlobalPart(std::vector<void*> &globalPart, UInt_t idx) override {{ }}
    Bool_t GlobalPartIsValid() const override {{ return true; }}

    Double_t operator()(Double_t t, const std::vector<Double_t> &param) const override;

    ClassDef({plugin_name}, 1)
}};
#endif
"""
        # 2. Implementation File (.cpp)
        cpp_code = f"""#include <cmath>
#include <vector>
#include "{plugin_name}.h"

ClassImp({plugin_name})

Double_t {plugin_name}::operator()(Double_t t, const std::vector<Double_t> &param) const {{
    return {cpp_math};
}}
"""
        # 3. ROOT LinkDef Specification Header
        linkdef_code = f"""#ifdef __CINT__
#pragma link off all globals;
#pragma link off all classes;
#pragma link off all functions;
#pragma link C++ class {plugin_name}+;
#endif
"""
        # Write structural code dependencies inside the targeted isolated directory
        with open(os.path.join(output_dir, f"{plugin_name}.h"), 'w') as f: f.write(h_code)
        with open(os.path.join(output_dir, f"{plugin_name}.cpp"), 'w') as f: f.write(cpp_code)
        with open(os.path.join(output_dir, f"{library_name}LinkDef.h"), 'w') as f: f.write(linkdef_code)
        
        # 4. Generate the Customized Makefile matching template parameters
        # Note: We include -I. so rootcling/g++ see local files when run inside the subdirectory.
        makefile_content = f"""# Generated Makefile for {library_name}
ROOTCFLAGS    = $(shell root-config --cflags)
ROOTLIBS      = $(shell root-config --libs)

CXX           = g++
CXXFLAGS      = -O3 -Wall -fPIC $(ROOTCFLAGS)
INCLUDES      = -I.

OBJS          = {plugin_name}.o {library_name}Dict.o
SHLIB         = lib{library_name}.so

all: $(SHLIB)

$(SHLIB): $(OBJS)
\t@echo "---> Building shared library $(SHLIB) ..."
\t$(CXX) $(OBJS) -shared -o $(SHLIB) $(ROOTLIBS)
\t@echo "done"

%.o: %.cpp
\t$(CXX) $(INCLUDES) $(CXXFLAGS) -c $<

{library_name}Dict.cpp: {plugin_name}.h {library_name}LinkDef.h
\t@echo "Generating ROOT dictionary $@..."
\trootcling -f $@ -c -p $(INCLUDES) $^

clean:
\trm -f $(OBJS) *Dict* $(SHLIB)
"""
        makefile_filename = f"Makefile.{library_name}"
        with open(os.path.join(output_dir, makefile_filename), 'w') as f:
            f.write(makefile_content)
            
        # 5. Execute Build Pass directly working inside the active subdirectory context
        print(f"   -> Launching external asset compilation via: make -f {makefile_filename}")
        try:
            # We use 'cwd' to run make entirely from within the subdirectory context 
            subprocess.run(["make", "-f", makefile_filename, "clean"], cwd=output_dir, check=True, capture_output=True)
            subprocess.run(["make", "-f", makefile_filename], cwd=output_dir, check=True, capture_output=True)
            print(f"   -> Successfully linked custom shared library asset inside '{output_dir}/lib{library_name}.so'.\n")
        except subprocess.CalledProcessError as err:
            print(f"[!] Compilation tracking error inside Makefile compilation pass!")
            if err.stderr:
                print(err.stderr.decode())
            raise err