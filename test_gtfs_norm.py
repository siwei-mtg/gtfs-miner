import os
import pandas as pd
from pathlib import Path
from gtfs_norm import rawgtfs_from_zip, gtfs_normalize
import traceback

def test_datasets():
    raw_dir = Path("Resources/raw")
    zip_files = list(raw_dir.glob("*.zip"))
    
    results = []
    
    for zip_path in zip_files:
        print(f"Testing {zip_path.name}...")
        res = {
            "name": zip_path.name,
            "status": "Success",
            "error": "",
            "metrics": {}
        }
        
        try:
            # 1. Load raw data
            # Note: We might need to modify rawgtfs_from_zip to handle encoding better
            raw_dict = rawgtfs_from_zip(zip_path)
            
            # 2. Normalize
            normed = gtfs_normalize(raw_dict)
            
            # 3. Collect metrics
            res["metrics"] = {
                "agency": len(normed['agency']),
                "routes": len(normed['routes']),
                "stops": len(normed['stops']),
                "trips": len(normed['trips']),
                "stop_times": len(normed['stop_times']),
                "initial_na": normed['initial_na'],
                "final_na_time": normed['final_na_time_col']
            }
            
        except Exception as e:
            res["status"] = "Failed"
            res["error"] = str(e)
            res["traceback"] = traceback.format_exc()
            print(f"  Failed: {e}")
            
        results.append(res)
    
    return results

def generate_report(results):
    report_path = "GTFS_Test_Report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# GTFS Normalization Test Report\n\n")
        f.write("| Dataset | Status | Agency | Routes | Stops | Trips | Stop Times | Error |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- | --- |\n")
        
        for res in results:
            m = res["metrics"]
            status_emoji = "✅" if res["status"] == "Success" else "❌"
            error_msg = res["error"].replace("\n", " ") if res["error"] else "-"
            
            f.write(f"| {res['name']} | {status_emoji} {res['status']} | "
                    f"{m.get('agency', '-')} | {m.get('routes', '-')} | "
                    f"{m.get('stops', '-')} | {m.get('trips', '-')} | "
                    f"{m.get('stop_times', '-')} | {error_msg} |\n")
        
        f.write("\n\n## Failure Details\n\n")
        for res in results:
            if res["status"] == "Failed":
                f.write(f"### {res['name']}\n")
                f.write(f"```python\n{res.get('traceback', '')}\n```\n\n")

if __name__ == "__main__":
    results = test_datasets()
    generate_report(results)
    print("Report generated: GTFS_Test_Report.md")
