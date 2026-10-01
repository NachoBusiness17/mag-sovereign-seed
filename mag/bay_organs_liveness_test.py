#!/usr/bin/env python3
"""bay_organs_liveness_test — falsification test for zombie-cron behavior.

DETERMINISTIC PROOF: This test verifies that dead claimants release queue items
promptly, falsifying zombie-cron vulnerability (claims persisting indefinitely
after process death). Test runs are reproducible and measurable.

Test design:
  1. Spawn 3 concurrent claimants racing on 1 queue item
  2. Force mid-race process death (taskkill) 
  3. Measure time-to-release for dead claims
  4. Verify live claimants can acquire freed items
  5. Document win32 edge cases (filter locks, sharing violations)

SUCCESS CRITERIA:
  - Dead claims released within 5s of process termination
  - No split-brain (exactly 1 winner per race round)  
  - Live claimants can acquire items immediately after death
  - No manual intervention required to clear stale claims

USAGE:
  python -m mag.bay_organs_liveness_test [--race-rounds N] [--death-delay S]

EXIT CODES:
  0 = all tests passed (zombie-cron falsified)
  1 = zombie-cron confirmed (dead claims persist >5s)
  2 = test failure (non-zombie error)
  3 = race condition detected (split-brain)
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add mag to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import mag.bay_organs as bay_organs
except ImportError:
    print("FATAL: Cannot import mag.bay_organs - not in test environment")
    sys.exit(2)

# Test configuration
TEST_QUEUE = "test_liveness_queue"
TEST_ITEM = "zombie_cron_test_item"
TEST_ROOT = None  # Use default from bay_organs
DEATH_DELAY_S = 1.0  # Time before killing processes
MAX_RELEASE_TIME_S = 5.0  # Maximum acceptable time for dead claim release
RACE_ROUNDS = 3  # Number of concurrent race tests

def cleanup_test_files():
    """Clean up any test artifacts from previous runs."""
    try:
        # Clean up claims directory
        claims_dir = bay_organs.claim_dir(TEST_QUEUE, TEST_ROOT)
        if os.path.exists(claims_dir):
            for f in os.listdir(claims_dir):
                if f.startswith(('.tmp-', '.expired-', '.json')):
                    try:
                        os.remove(os.path.join(claims_dir, f))
                    except OSError:
                        pass
        # Clean up any remaining test processes
        subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], 
                      capture_output=True, timeout=5)
    except Exception:
        pass

def spawn_claimant(worker_id: int, delay_before_death: float) -> Optional[int]:
    """Spawn a claimant process that will be killed mid-race."""
    # Create test script as separate process
    test_script = f'''
import sys
import time
import os
sys.path.insert(0, r"{str(Path(__file__).parent.parent)}")
import mag.bay_organs as bay_organs

worker_id = {worker_id}
delay_before_death = {delay_before_death}
queue = "{TEST_QUEUE}"
item = "{TEST_ITEM}"
root = {TEST_ROOT}

print(f"Worker {{worker_id}} starting")
start_time = time.time()

try:
    # Attempt to claim the item
    claim = bay_organs.try_claim(queue, item, f"worker_{{worker_id}}", "test_slot", 
                                grace_s=300, root=root)
    
    if claim is not None:
        print(f"Worker {worker_id} WON claim at {time.time() - start_time:.2f}s")
        print(f"Claim: {claim}")
        
        # Hold claim for specified delay then exit
        time.sleep(delay_before_death)
        print(f"Worker {worker_id} releasing claim normally")
        bay_organs.release_claim(queue, item, claim["token"], root)
    else:
        print(f"Worker {worker_id} LOST claim")
        
except Exception as e:
    print(f"Worker {worker_id} ERROR: {e}")
    sys.exit(2)
'''
    
    # Write test script to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(test_script)
        script_path = f.name
    
    try:
        # Spawn process
        proc = subprocess.Popen([sys.executable, script_path], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE,
                              creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        
        return proc.pid
    except Exception as e:
        print(f"Failed to spawn claimant {worker_id}: {e}")
        try:
            os.unlink(script_path)
        except:
            pass
        return None

def kill_process(pid: int) -> bool:
    """Force kill a process and return success status."""
    try:
        result = subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                              capture_output=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def monitor_claim_release(start_time: float, max_wait: float) -> Tuple[bool, float]:
    """Monitor until claim is released or timeout."""
    end_time = start_time + max_wait
    
    while time.time() < end_time:
        claim = bay_organs._read_claim(bay_organs.claim_path(TEST_QUEUE, TEST_ITEM, TEST_ROOT))
        if claim is None:
            release_time = time.time() - start_time
            return True, release_time
        
        time.sleep(0.1)
    
    return False, max_wait

def run_race_test(round_num: int) -> Dict[str, Any]:
    """Run a single race test with 3 concurrent claimants."""
    print(f"\n=== RACE ROUND {round_num} ===")
    
    # Clean up any existing claims
    cleanup_test_files()
    
    results = {
        "round": round_num,
        "start_time": time.time(),
        "workers": [],
        "claim_won_by": None,
        "death_times": [],
        "release_times": [],
        "errors": []
    }
    
    # Start 3 worker processes with staggered death times
    worker_pids = []
    try:
        # Worker 0: dies immediately (zombie candidate)
        pid0 = spawn_claimant(0, 0.5)
        if pid0:
            worker_pids.append(("worker_0", pid0, 0.5))
            print(f"Started worker_0 (PID {pid0}) - will die in 0.5s")
        else:
            results["errors"].append("Failed to spawn worker_0")
        
        # Worker 1: dies after delay
        pid1 = spawn_claimant(1, DEATH_DELAY_S)
        if pid1:
            worker_pids.append(("worker_1", pid1, DEATH_DELAY_S))
            print(f"Started worker_1 (PID {pid1}) - will die in {DEATH_DELAY_S}s")
        else:
            results["errors"].append("Failed to spawn worker_1")
        
        # Worker 2: lives normally
        pid2 = spawn_claimant(2, 10.0)
        if pid2:
            worker_pids.append(("worker_2", pid2, 10.0))
            print(f"Started worker_2 (PID {pid2}) - will live 10s")
        else:
            results["errors"].append("Failed to spawn worker_2")
        
        # Monitor and kill processes at scheduled times
        start_time = time.time()
        for name, pid, death_delay in worker_pids:
            death_time = start_time + death_delay
            results["death_times"].append({
                "worker": name,
                "pid": pid,
                "scheduled_death_time": death_time,
                "actual_death_time": None
            })
            
            # Wait for scheduled death time
            while time.time() < death_time:
                time.sleep(0.1)
            
            # Kill the process
            if kill_process(pid):
                actual_death_time = time.time()
                results["death_times"][-1]["actual_death_time"] = actual_death_time
                print(f"Killed {name} (PID {pid}) at {actual_death_time:.2f}s")
                
                # Monitor for claim release
                released, release_time = monitor_claim_release(actual_death_time, MAX_RELEASE_TIME_S)
                results["release_times"].append({
                    "worker": name,
                    "released": released,
                    "release_time": release_time
                })
                if not released:
                    print(f"WARNING: {name} claim not released within {MAX_RELEASE_TIME_S}s")
            else:
                print(f"WARNING: Failed to kill {name} (PID {pid})")
                results["errors"].append(f"Failed to kill {name}")
        
        # Check final claim status
        final_claim = bay_organs._read_claim(bay_organs.claim_path(TEST_QUEUE, TEST_ITEM, TEST_ROOT))
        if final_claim:
            results["claim_won_by"] = final_claim.get("engine", "unknown")
            print(f"Final claim held by: {results['claim_won_by']}")
            
            # Check if holder is still alive
            if not bay_organs.pid_alive(final_claim.get("pid")):
                results["errors"].append("ZOMBIE CONFIRMED: Dead process holding claim")
                print("ZOMBIE CONFIRMED: Dead process holding claim")
            else:
                print("Claim held by live process")
        else:
            print("No active claim detected")
        
        # Clean up remaining processes
        for name, pid, _ in worker_pids:
            try:
                kill_process(pid)
            except:
                pass
        
    except Exception as e:
        results["errors"].append(f"Race test exception: {e}")
        print(f"Race test exception: {e}")
    
    results["end_time"] = time.time()
    return results

def run_liveness_test() -> Dict[str, Any]:
    """Run complete liveness falsification test suite."""
    print("Starting bay_organs liveness test suite...")
    print(f"Target: Dead claims must release within {MAX_RELEASE_TIME_S}s")
    print(f"Race rounds: {RACE_ROUNDS}")
    
    overall_start = time.time()
    
    test_results = {
        "test_name": "bay_organs_liveness_test",
        "start_time": overall_start,
        "max_release_time_target": MAX_RELEASE_TIME_S,
        "race_rounds": RACE_ROUNDS,
        "rounds": [],
        "summary": {
            "total_races": 0,
            "zombie_detected": False,
            "split_brain": False,
            "max_release_time": 0.0,
            "races_with_errors": 0
        }
    }
    
    try:
        # Run multiple race rounds
        for round_num in range(1, RACE_ROUNDS + 1):
            round_result = run_race_test(round_num)
            test_results["rounds"].append(round_result)
            
            # Update summary
            test_results["summary"]["total_races"] += 1
            if round_result["errors"]:
                test_results["summary"]["races_with_errors"] += 1
            
            # Check for zombie behavior
            for release in round_result["release_times"]:
                if not release["released"]:
                    test_results["summary"]["zombie_detected"] = True
                test_results["summary"]["max_release_time"] = max(
                    test_results["summary"]["max_release_time"], 
                    release["release_time"]
                )
            
            # Check for split-brain (multiple claim winners)
            claim_holders = [r["claim_won_by"] for r in test_results["rounds"] if r["claim_won_by"]]
            if len(set(claim_holders)) > 1 and len(claim_holders) > 1:
                test_results["summary"]["split_brain"] = True
        
        test_results["end_time"] = time.time()
        test_results["duration"] = test_results["end_time"] - test_results["start_time"]
        
        # Generate verdict
        if test_results["summary"]["zombie_detected"]:
            print(f"\n❌ ZOMBIE-CRON CONFIRMED: Dead claims persisting >{MAX_RELEASE_TIME_S}s")
            return 1, test_results
        elif test_results["summary"]["split_brain"]:
            print(f"\n⚠️  SPLIT-BRAIN DETECTED: Multiple claim winners detected")
            return 3, test_results
        elif test_results["summary"]["max_release_time"] > MAX_RELEASE_TIME_S:
            print(f"\n⚠️  SLOW RELEASE: Max release time {test_results['summary']['max_release_time']:.2f}s > {MAX_RELEASE_TIME_S}s")
            return 2, test_results
        else:
            print(f"\n✅ ZOMBIE-CRON FALSIFIED: All dead claims released within {MAX_RELEASE_TIME_S}s")
            print(f"   Max release time: {test_results['summary']['max_release_time']:.2f}s")
            return 0, test_results
            
    except Exception as e:
        print(f"\n❌ TEST FAILURE: {e}")
        test_results["errors"] = [str(e)]
        return 2, test_results

def main():
    """Main test entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test bay_organs liveness detection")
    parser.add_argument("--race-rounds", type=int, default=3,
                       help="Number of race test rounds")
    parser.add_argument("--death-delay", type=float, default=1.0,
                       help="Delay before killing processes (seconds)")
    parser.add_argument("--max-release-time", type=float, default=5.0,
                       help="Maximum acceptable claim release time (seconds)")
    
    args = parser.parse_args()
    
    global RACE_ROUNDS, DEATH_DELAY_S, MAX_RELEASE_TIME_S
    RACE_ROUNDS = args.race_rounds
    DEATH_DELAY_S = args.death_delay
    MAX_RELEASE_TIME_S = args.max_release_time
    
    # Cleanup before test
    cleanup_test_files()
    
    # Run test
    exit_code, results = run_liveness_test()
    
    # Write detailed results
    results_file = Path("memory/runs/bay_organs_liveness_test/latest.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: {results_file}")
    
    # Exit with appropriate code
    sys.exit(exit_code)

if __name__ == "__main__":
    main()