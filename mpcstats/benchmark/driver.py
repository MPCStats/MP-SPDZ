#!/usr/bin/env python3

from pathlib import Path
repo_root = Path(__file__).parent.parent.parent
benchmark_dir = repo_root / 'mpcstats' / 'benchmark'
computation_def_dir = benchmark_dir / 'computation_defs'

import subprocess
import json
from protocols import all_protocols
from constants import COMPUTATION, PROTOCOL, CATEGORY, ROUNDS, COMPILATION_TIME, TIME_SEC, COMPILE_MAX_MEM_USAGE_KB, EXECUTOR_MAX_MEM_USAGE_KB, TOTAL_BYTECODE_SIZE, EXECUTOR_EXEC_TIME_SEC, COMPILE_EXEC_TIME_SEC, STATISTICAL_SECURITY_PARAMETER, DATA_SENT_BY_PARTY_0, GLOBAL_DATA_SENT_MB, RESULT

COMP='comp'
EXEC='exec'
META='meta'

headers = [
    (COMPUTATION, META),
    (PROTOCOL, EXEC),
    (CATEGORY, META),
    (ROUNDS, EXEC),
    (COMPILATION_TIME, COMP),
    (TIME_SEC, EXEC),
    (COMPILE_MAX_MEM_USAGE_KB, COMP),
    (EXECUTOR_MAX_MEM_USAGE_KB, EXEC),
    (TOTAL_BYTECODE_SIZE, COMP),
    #(EXECUTOR_EXEC_TIME_SEC, EXEC),
    #(COMPILE_EXEC_TIME_SEC, COMP),
    (STATISTICAL_SECURITY_PARAMETER, EXEC),
    (DATA_SENT_BY_PARTY_0, EXEC),
    (GLOBAL_DATA_SENT_MB, EXEC),
    (RESULT, EXEC),
]

def gen_header() -> str:
    return ','.join([header[0] for header in headers])

def gen_line(result: object) -> str:
    comp = result[0] # compilation stats
    exe = result[1] # execution stats
    meta = result[2] # meta data

    cols = []
    for header in headers:
        key = header[0]
        typ = header[1]

        col = ''
        if comp != {} and typ == COMP:
            col = str(comp[key])
        elif exe != {} and typ == EXEC:
            col = str(exe[key])
        elif meta != {} and typ == META:
            col = str(meta[key])
        cols.append(col)

    return ','.join(cols)

def write_benchmark_result(computation_def: Path, protocol: str, program: str, category: str) -> None:
    cmd = [benchmark_dir / 'benchmarker.py', protocol, '--file', computation_def]
    result = subprocess.run(cmd, capture_output=True, text=True)
    result_obj = json.loads(result.stdout)
    result_obj.append({
        'computation': computation_def.stem,
        'category': category,
    })
    print(gen_line(result_obj))

subprocess.run([benchmark_dir / 'gen_comp_defs.py'], check=True)

# print header
print(gen_header())

# List all files in the directory
computation_defs = [file for file in computation_def_dir.iterdir() if file.is_file()]

# print benchmark result rows
for computation_def in computation_defs:
    for protocol, program, category in all_protocols:
        if protocol != '':
            write_benchmark_result(computation_def, protocol, program, category)

