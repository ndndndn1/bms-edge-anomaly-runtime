#!/usr/bin/env bash
set -euo pipefail

build_dir="${1:-build/quality}"
mkdir -p "$build_dir"

common=(-std=c++17 -Wall -Wextra -Werror -fno-omit-frame-pointer)
g++ "${common[@]}" -O1 -g -fsanitize=address,undefined \
  cpp/bms_core.cpp cpp/test_core.cpp -o "$build_dir/test_core_sanitized"
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 \
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
  "$build_dir/test_core_sanitized"

gcc -std=c11 -Wall -Wextra -Werror -c cpp/test_c_abi.c -o "$build_dir/test_c_abi.o"
g++ "$build_dir/test_c_abi.o" cpp/bms_core.cpp -o "$build_dir/test_c_abi"
"$build_dir/test_c_abi"

g++ "${common[@]}" -O2 cpp/bms_core.cpp cpp/benchmark_core.cpp -o "$build_dir/benchmark_core"
"$build_dir/benchmark_core" "${BMS_BENCH_ITERATIONS:-100000}"
