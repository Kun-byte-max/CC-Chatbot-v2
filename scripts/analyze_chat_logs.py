#!/usr/bin/env python3
import fileinput
import json
import math
import re
import sys
from collections import defaultdict
from typing import List, Dict, Any, Optional

PATTERN = re.compile(
    r'chat_turn\s+'
    r'request_id=(?P<request_id>\S+)\s+'
    r'role=(?P<role>\S+)\s+'
    r'intent_hint=(?P<intent_hint>\S+)\s+'
    r'msg_len=(?P<msg_len>\d+)\s+'
    r'stages=(?P<stages>\{.*?\})\s+'
    r'total_ms=(?P<total_ms>\d+)\s+'
    r'outcome=(?P<outcome>\S+)'
)

def calc_percentile(vals: List[float], p: float) -> float:
    if not vals:
        return 0.0
    sorted_vals = sorted(vals)
    idx = (len(sorted_vals) - 1) * (p / 100.0)
    floor_idx = int(math.floor(idx))
    ceil_idx = int(math.ceil(idx))
    if floor_idx == ceil_idx:
        return float(sorted_vals[floor_idx])
    weight = idx - floor_idx
    return sorted_vals[floor_idx] * (1.0 - weight) + sorted_vals[ceil_idx] * weight

def calc_stdev(vals: List[float]) -> float:
    if len(vals) <= 1:
        return 0.0
    mean_val = sum(vals) / len(vals)
    variance = sum((x - mean_val) ** 2 for x in vals) / (len(vals) - 1)
    return math.sqrt(variance)

def read_log_lines() -> List[str]:
    lines = []
    files = sys.argv[1:] if len(sys.argv) > 1 else []
    if not files:
        return sys.stdin.readlines()
    for fname in files:
        try:
            with open(fname, "r", encoding="utf-8") as f:
                lines.extend(f.readlines())
        except UnicodeDecodeError:
            with open(fname, "r", encoding="utf-16") as f:
                lines.extend(f.readlines())
    return lines

def parse_bool(val: Optional[str]) -> Optional[bool]:
    if val is None:
        return None
    return val.lower() == "true"

def main():
    turns = []
    lines = read_log_lines()
    
    for line in lines:
        match = PATTERN.search(line)
        if match:
            d = match.groupdict()
            try:
                stages = json.loads(d["stages"])
            except Exception:
                stages = {}

            p_ran = re.search(r'profile_parse_ran=(\S+)', line)
            s_ran = re.search(r'search_parse_ran=(\S+)', line)
            p_tok = re.search(r'compose_prompt_tokens=(-?\d+)', line)
            c_tok = re.search(r'compose_completion_tokens=(-?\d+)', line)
            p_found = re.search(r'profile_found=(\S+)', line)
            sq_found = re.search(r'search_query_found=(\S+)', line)
            s_exec = re.search(r'search_executed=(\S+)', line)

            turns.append({
                "request_id": d["request_id"],
                "role": d["role"],
                "intent_hint": d["intent_hint"],
                "msg_len": int(d["msg_len"]),
                "stages": stages,
                "total_ms": int(d["total_ms"]),
                "outcome": d["outcome"],
                "profile_parse_ran": parse_bool(p_ran.group(1)) if p_ran else None,
                "search_parse_ran": parse_bool(s_ran.group(1)) if s_ran else None,
                "compose_prompt_tokens": int(p_tok.group(1)) if p_tok else -1,
                "compose_completion_tokens": int(c_tok.group(1)) if c_tok else -1,
                "profile_found": parse_bool(p_found.group(1)) if p_found else None,
                "search_query_found": parse_bool(sq_found.group(1)) if sq_found else None,
                "search_executed": parse_bool(s_exec.group(1)) if s_exec else None,
            })

    total_turns = len(turns)
    print("==================================================")
    print("CHAT TURN LATENCY BASELINE ANALYSIS")
    print("==================================================")
    print(f"Total Chat Turns Analyzed: {total_turns}\n")

    if total_turns == 0:
        print("No chat_turn log entries found.")
        return

    # 1. Turn count broken down by role and intent_hint
    role_counts = defaultdict(int)
    intent_counts = defaultdict(int)
    role_intent_counts = defaultdict(lambda: defaultdict(int))
    for t in turns:
        r = t["role"]
        i = t["intent_hint"]
        role_counts[r] += 1
        intent_counts[i] += 1
        role_intent_counts[r][i] += 1

    print("--- Turn Counts ---")
    print("By Role:")
    for r, count in sorted(role_counts.items()):
        print(f"  {r:<12}: {count}")
    print("\nBy Intent Hint:")
    for i, count in sorted(intent_counts.items()):
        print(f"  {i:<12}: {count}")
    print("\nBy Role & Intent Hint:")
    for r in sorted(role_intent_counts.keys()):
        for i, count in sorted(role_intent_counts[r].items()):
            print(f"  {r:<10} / {i:<12}: {count}")
    print()

    # 2. Stage Summary: Count, Mean, StdDev, Min, Max, p50, p90, p99
    stage_durations = defaultdict(list)
    for t in turns:
        for stage_name, duration_ms in t["stages"].items():
            stage_durations[stage_name].append(float(duration_ms))

    print("--- Detailed Stage Summary (ms) ---")
    header = f"{'Stage':<16} | {'Count':<5} | {'Mean':<8} | {'StdDev':<8} | {'Min':<6} | {'Max':<6} | {'p50':<7} | {'p90':<7} | {'p99':<10}"
    print(header)
    print("-" * len(header))

    for stage_name in sorted(stage_durations.keys()):
        durations = stage_durations[stage_name]
        cnt = len(durations)
        mean_val = sum(durations) / cnt
        std_val = calc_stdev(durations)
        min_val = min(durations)
        max_val = max(durations)
        p50_val = calc_percentile(durations, 50)
        p90_val = calc_percentile(durations, 90)
        
        if cnt < 20:
            p99_str = "n/a (n<20)"
        else:
            p99_str = f"{calc_percentile(durations, 99):<10.1f}"

        print(f"{stage_name:<16} | {cnt:<5} | {mean_val:<8.1f} | {std_val:<8.1f} | {min_val:<6.0f} | {max_val:<6.0f} | {p50_val:<7.1f} | {p90_val:<7.1f} | {p99_str}")
    print()

    # 3. Stage-Share Table: mean stage cost as % of total_ms, grouped by intent_hint
    intent_turns = defaultdict(list)
    for t in turns:
        intent_turns[t["intent_hint"]].append(t)

    print("--- Stage-Share Table (% of Mean total_ms) ---")
    for intent_name in sorted(intent_turns.keys()):
        i_turns = intent_turns[intent_name]
        n_turns = len(i_turns)
        mean_total = sum(t["total_ms"] for t in i_turns) / float(n_turns) if n_turns else 1.0

        i_stage_durations = defaultdict(list)
        for t in i_turns:
            for s_name, s_ms in t["stages"].items():
                i_stage_durations[s_name].append(float(s_ms))

        print(f"\nIntent: {intent_name.upper()} (n={n_turns}, Mean Total = {mean_total:.1f} ms)")
        print(f"  {'Stage':<16} | {'Runs':<5} | {'Mean Stage ms':<13} | {'Share of total_ms':<18}")
        print("  " + "-" * 58)

        for s_name in sorted(i_stage_durations.keys()):
            s_durs = i_stage_durations[s_name]
            s_cnt = len(s_durs)
            s_mean = sum(s_durs) / float(s_cnt) if s_cnt else 0.0
            share_pct = (sum(s_durs) / (mean_total * n_turns)) * 100.0 if mean_total > 0 else 0.0
            print(f"  {s_name:<16} | {s_cnt:<5} | {s_mean:<13.1f} | {share_pct:<18.1f}%")

    print()

    # 4. Compose Token Accounting Summary (Part D)
    print("--- Compose Token Accounting Summary ---")
    intent_tokens = defaultdict(lambda: {"prompt": [], "completion": []})
    for t in turns:
        if t["compose_prompt_tokens"] >= 0:
            intent_tokens[t["intent_hint"]]["prompt"].append(t["compose_prompt_tokens"])
        if t["compose_completion_tokens"] >= 0:
            intent_tokens[t["intent_hint"]]["completion"].append(t["compose_completion_tokens"])

    for intent_name in sorted(intent_tokens.keys()):
        p_toks = intent_tokens[intent_name]["prompt"]
        c_toks = intent_tokens[intent_name]["completion"]
        p_mean = sum(p_toks) / len(p_toks) if p_toks else 0.0
        c_mean = sum(c_toks) / len(c_toks) if c_toks else 0.0
        print(f"Intent: {intent_name.upper()} (n={len(p_toks)})")
        print(f"  Prompt Tokens    : Mean = {p_mean:.1f} | Min = {min(p_toks) if p_toks else 0} | Max = {max(p_toks) if p_toks else 0}")
        print(f"  Completion Tokens: Mean = {c_mean:.1f} | Min = {min(c_toks) if c_toks else 0} | Max = {max(c_toks) if c_toks else 0}")
    print()

    # 5. Gate Execution & Regression Check Metrics
    profile_parse_count = len(stage_durations.get("profile_parse", []))
    search_parse_count = len(stage_durations.get("search_parse", []))
    search_http_count = len(stage_durations.get("search_http", []))
    profile_write_count = len(stage_durations.get("profile_write", []))
    rank_count = len(stage_durations.get("rank", []))

    print("--- Gate Execution & Regression Check Metrics ---")
    print(f"  profile_parse runs: {profile_parse_count} / {total_turns}")
    print(f"  search_parse  runs: {search_parse_count} / {total_turns}")
    print(f"  search_http   runs: {search_http_count} (target = 19)")
    print(f"  profile_write runs: {profile_write_count} (target = 4)")
    print(f"  rank          runs: {rank_count} (target = 16)\n")

    # 6. Overall total_ms stats
    all_totals = [float(t["total_ms"]) for t in turns]
    overall_mean = sum(all_totals) / len(all_totals) if all_totals else 0.0
    overall_std = calc_stdev(all_totals)
    overall_p90 = calc_percentile(all_totals, 90)

    print("--- Overall Total Duration (total_ms) Summary ---")
    print(f"Mean: {overall_mean:.1f} ms | StdDev: {overall_std:.1f} ms | p50: {calc_percentile(all_totals, 50):.1f} ms | p90: {overall_p90:.1f} ms\n")

if __name__ == "__main__":
    main()
