import os
import json
import time
import urllib.request
import urllib.error
from agent_tracer_plus.utils.logger import get_logger

logger = get_logger("cli.eval")

def run_eval(dataset_id: str, prompt_id: str, name: str, host: str = "http://localhost:3000"):
    api_key = os.getenv("ATP_API_KEY", "sk_default")
    pub_key = os.getenv("ATP_PUBLIC_KEY", "pk_default")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "X-Public-Key": pub_key
    }
    
    payload = {
        "name": name,
        "dataset_id": dataset_id,
        "prompt_id": prompt_id
    }
    
    logger.info(f"Triggering evaluation run '{name}' for dataset {dataset_id} with prompt {prompt_id}...")
    
    try:
        req = urllib.request.Request(
            f"{host}/api/experiments/run", 
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            exp_id = data.get("experiment_id")
            
        logger.info(f"Evaluation triggered successfully. Experiment ID: {exp_id}")
        logger.info("Waiting for results...")
        
        # Poll for results (simple delay for MVP)
        time.sleep(3)
        
        req = urllib.request.Request(f"{host}/api/experiments/{exp_id}/results", headers=headers)
        with urllib.request.urlopen(req) as res:
            result_data = json.loads(res.read().decode())
            results = result_data.get("results", [])
            
        if not results:
            logger.warning("No results found. The evaluation might still be running.")
            return
            
        successes = sum(1 for r in results if r.get("success"))
        total = len(results)
        success_rate = (successes / total) * 100 if total > 0 else 0
        avg_latency = sum(r.get("latency", 0) for r in results) / total if total > 0 else 0
        
        print("\n=== Evaluation Results ===")
        print(f"Total Datapoints : {total}")
        print(f"Success Rate     : {success_rate:.1f}%")
        print(f"Avg Latency      : {avg_latency:.2f}s")
        print("==========================\n")
        
        # Could exit with non-zero code if success rate < threshold for CI/CD pipelines
        if success_rate < 80.0:
            logger.warning("Success rate below 80%. Check logs for details.")
        
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP Error: {e.code} - {e.read().decode()}")
    except Exception as e:
        logger.error(f"Failed to run evaluation: {e}")
