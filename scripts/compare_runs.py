#!/usr/bin/env python3
import json
import re
import sys
from typing import Dict, Any, List

def parse_log_file(log_path: str, id_list_path: str) -> List[Dict[str, Any]]:
    with open(id_list_path, "r", encoding="utf-8") as f:
        target_ids = [line.strip() for line in f if line.strip()]

    if len(target_ids) != 30:
        raise ValueError(f"Expected 30 IDs in {id_list_path}, found {len(target_ids)}")

    lines = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        with open(log_path, "r", encoding="utf-16") as f:
            lines = f.readlines()

    id_to_turn = {}
    pattern = re.compile(r'chat_turn\s+request_id=(?P<request_id>\S+)\s+')

    for line in lines:
        match = pattern.search(line)
        if match:
            req_id = match.group("request_id")
            
            # Extract key-value pairs
            role_m = re.search(r'role=(\S+)', line)
            intent_m = re.search(r'intent_hint=(\S+)', line)
            stages_m = re.search(r'stages=(\{.*?\})', line)
            msg_len_m = re.search(r'msg_len=(\d+)', line)
            
            p_ran_m = re.search(r'profile_parse_ran=(\S+)', line)
            s_ran_m = re.search(r'search_parse_ran=(\S+)', line)
            p_found_m = re.search(r'profile_found=(\S+)', line)
            sq_found_m = re.search(r'search_query_found=(\S+)', line)
            s_exec_m = re.search(r'search_executed=(\S+)', line)

            stages = {}
            if stages_m:
                try:
                    stages = json.loads(stages_m.group(1))
                except Exception:
                    pass

            id_to_turn[req_id] = {
                "request_id": req_id,
                "role": role_m.group(1) if role_m else "unknown",
                "intent_hint": intent_m.group(1) if intent_m else "unknown",
                "msg_len": int(msg_len_m.group(1)) if msg_len_m else 0,
                "stages": stages,
                "profile_parse_ran": p_ran_m.group(1) == "true" if p_ran_m else ("profile_parse" in stages),
                "search_parse_ran": s_ran_m.group(1) == "true" if s_ran_m else ("search_parse" in stages),
                "profile_found": p_found_m.group(1) == "true" if p_found_m else ("profile_write" in stages),
                "search_query_found": sq_found_m.group(1) == "true" if sq_found_m else ("search_http" in stages),
                "search_executed": s_exec_m.group(1) == "true" if s_exec_m else ("search_http" in stages),
                "has_profile_write": "profile_write" in stages,
                "has_search_http": "search_http" in stages,
                "has_rank": "rank" in stages,
                "raw_line": line.strip(),
            }

    aligned_turns = []
    missing_ids = []
    for req_id in target_ids:
        if req_id in id_to_turn:
            aligned_turns.append(id_to_turn[req_id])
        else:
            missing_ids.append(req_id)

    if missing_ids:
        raise ValueError(f"Log {log_path} missing {len(missing_ids)} IDs from {id_list_path}: {missing_ids}")

    return aligned_turns

def main():
    base_log = sys.argv[1] if len(sys.argv) > 1 else "baseline_run.log"
    step1_log = sys.argv[2] if len(sys.argv) > 2 else "step1_run.log"
    base_ids = "baseline_request_ids.txt"
    step1_ids = "step1_ids.txt"

    base_turns = parse_log_file(base_log, base_ids)
    step1_turns = parse_log_file(step1_log, step1_ids)

    print("=========================================================================================================")
    print("POSITIONAL RECONCILIATION TABLE: BASELINE VS STEP1 (30 TURNS ALIGNED BY REQUEST ID)")
    print("=========================================================================================================")
    header = f"{'Pos':<4} | {'Role':<8} | {'BASELINE (intent, s_exec, p_write, s_http, rank)':<42} | {'STEP1 (intent, s_exec, p_write, s_http, rank)':<42}"
    print(header)
    print("-" * len(header))

    seq_messages = [
        "Emp #1: hi",
        "Emp #2: thanks",
        "Emp #3: what are my skills?",
        "Emp #4: add Python and Django to my skills",
        "Emp #5: I have 4 years of experience in backend development",
        "Emp #6: show me python jobs in Pune",
        "Emp #7: only remote ones",
        "Emp #8: something with better pay",
        "Emp #9: show me data analyst jobs",
        "Emp #10: tell me about the second job",
        "Empr #1: I need a senior backend engineer",
        "Empr #2: with 5 years experience",
        "Empr #3: in Bangalore",
        "Empr #4: show me more candidates",
        "Empr #5: hi",
    ]

    profile_write_drops = []
    search_http_drops = []
    rank_drops = []

    for i in range(30):
        pos = i + 1
        b = base_turns[i]
        s = step1_turns[i]
        role = s["role"]

        b_str = f"{b['intent_hint']:<9}, s_exec={str(b['search_executed']):<5}, p_write={str(b['has_profile_write']):<5}, s_http={str(b['has_search_http']):<5}, rank={str(b['has_rank']):<5}"
        s_str = f"{s['intent_hint']:<9}, s_exec={str(s['search_executed']):<5}, p_write={str(s['has_profile_write']):<5}, s_http={str(s['has_search_http']):<5}, rank={str(s['has_rank']):<5}"

        print(f"{pos:<4} | {role:<8} | {b_str} | {s_str}")

        if b["has_profile_write"] and not s["has_profile_write"]:
            profile_write_drops.append((pos, b, s))
        if b["has_search_http"] and not s["has_search_http"]:
            search_http_drops.append((pos, b, s))
        if b["has_rank"] and not s["has_rank"]:
            rank_drops.append((pos, b, s))

    print("\n=========================================================================================================")
    print("DETAILED QUESTION RECONCILIATIONS")
    print("=========================================================================================================")

    print(f"\nA1 — Lost profile_write turns (Baseline 4 -> Step1 3, Drop count: {len(profile_write_drops)}):")
    for pos, b, s in profile_write_drops:
        msg_text = seq_messages[(pos - 1) % 15]
        print(f"  - Position {pos} ({msg_text}):")
        print(f"    Baseline ID: {b['request_id']} (intent={b['intent_hint']}, p_write={b['has_profile_write']})")
        print(f"    Step1 ID   : {s['request_id']} (intent={s['intent_hint']}, p_write={s['has_profile_write']}, p_parse_ran={s['profile_parse_ran']}, p_found={s['profile_found']})")

    print(f"\nA2 — Lost search_http turns (Baseline 19 -> Step1 17, Drop count: {len(search_http_drops)}):")
    for pos, b, s in search_http_drops:
        msg_text = seq_messages[(pos - 1) % 15]
        print(f"  - Position {pos} ({msg_text}):")
        print(f"    Baseline ID: {b['request_id']} (intent={b['intent_hint']}, s_http={b['has_search_http']})")
        print(f"    Step1 ID   : {s['request_id']} (intent={s['intent_hint']}, s_http={s['has_search_http']}, s_parse_ran={s['search_parse_ran']}, sq_found={s['search_query_found']}, s_exec={s['search_executed']})")

    print(f"\nA3 — Lost rank turns (Baseline 16 -> Step1 14, Drop count: {len(rank_drops)}):")
    for pos, b, s in rank_drops:
        msg_text = seq_messages[(pos - 1) % 15]
        print(f"  - Position {pos} ({msg_text}):")
        print(f"    Baseline ID: {b['request_id']} (rank={b['has_rank']})")
        print(f"    Step1 ID   : {s['request_id']} (rank={s['has_rank']})")

if __name__ == "__main__":
    main()
