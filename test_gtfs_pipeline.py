import os
import pandas as pd
from pathlib import Path
import traceback

from gtfs_norm import rawgtfs_from_zip, gtfs_normalize
from gtfs_spatial import ag_ap_generate_reshape
from gtfs_generator import itineraire_generate, course_generate
from gtfs_export import MEF_ligne, MEF_course, MEF_iti

def test_pipeline():
    raw_dir = Path("Resources/raw")
    zip_files = list(raw_dir.glob("*.zip"))
    
    results = []
    
    for zip_path in zip_files:
        print(f"Testing {zip_path.name}...")
        res = {
            "name": zip_path.name,
            "norm": {"status": "Pending", "error": ""},
            "spatial": {"status": "Pending", "error": ""},
            "generator": {"status": "Pending", "error": ""},
            "export": {"status": "Pending", "error": ""},
            "metrics": {}
        }
        
        # 1. Norm Module
        try:
            raw_dict = rawgtfs_from_zip(zip_path)
            normed = gtfs_normalize(raw_dict)
            res["norm"]["status"] = "Success"
            res["metrics"]["stops"] = len(normed['stops'])
            res["metrics"]["trips"] = len(normed['trips'])
        except Exception as e:
            res["norm"]["status"] = "Failed"
            res["norm"]["error"] = f"{type(e).__name__}: {str(e)}"
            results.append(res)
            print(f"  Norm Failed: {e}")
            continue
            
        # 2. Spatial Module
        try:
            AP, AG, marker = ag_ap_generate_reshape(normed['stops'])
            res["spatial"]["status"] = "Success"
            res["metrics"]["AP"] = len(AP)
            res["metrics"]["AG"] = len(AG)
        except Exception as e:
            res["spatial"]["status"] = "Failed"
            res["spatial"]["error"] = f"{type(e).__name__}: {str(e)}"
            results.append(res)
            print(f"  Spatial Failed: {e}")
            continue
            
        # 3. Generator Module
        try:
            if normed['stop_times'].empty:
                raise ValueError("stop_times data is empty")
            itineraire = itineraire_generate(normed['stop_times'], AP, normed['trips'])
            courses = course_generate(itineraire)
            res["generator"]["status"] = "Success"
            res["metrics"]["itineraire"] = len(itineraire)
            res["metrics"]["courses"] = len(courses)
        except Exception as e:
            res["generator"]["status"] = "Failed"
            res["generator"]["error"] = f"{type(e).__name__}: {str(e)}"
            results.append(res)
            print(f"  Generator Failed: {e}")
            continue
            
        # 4. Export Module
        try:
            lignes = normed['routes']
            mef_lignes = MEF_ligne(lignes, courses, AG)
            mef_course = MEF_course(courses, normed['trip_id_coor'])
            mef_iti = MEF_iti(itineraire, courses)
            res["export"]["status"] = "Success"
            res["metrics"]["export_rows"] = len(mef_iti)
        except Exception as e:
            res["export"]["status"] = "Failed"
            res["export"]["error"] = f"{type(e).__name__}: {str(e)}"
            results.append(res)
            print(f"  Export Failed: {e}")
            continue
            
        results.append(res)
        
    return results

def generate_md_report(results):
    report_path = "GTFS_Unit_Test_Report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# GTFS Pipeline Unit Test Report\n\n")
        f.write("该报表基于 `Resources/raw` 中的实际数据集，对 `gtfs_norm`, `gtfs_spatial`, `gtfs_generator`, `gtfs_export` 进行逐个顺序测试。\n\n")
        
        f.write("## 模块运行状态总览\n\n")
        f.write("| Dataset | `gtfs_norm` | `gtfs_spatial` | `gtfs_generator` | `gtfs_export` |\n")
        f.write("| --- | --- | --- | --- | --- |\n")
        
        for r in results:
            def to_emoji(status):
                if status == "Success": return "✅ Success"
                elif status == "Failed": return "❌ Failed"
                return "⏸️ Skipped"
            
            n = to_emoji(r["norm"]["status"])
            s = to_emoji(r["spatial"]["status"])
            g = to_emoji(r["generator"]["status"])
            e = to_emoji(r["export"]["status"])
            
            f.write(f"| {r['name']} | {n} | {s} | {g} | {e} |\n")
            
        f.write("\n\n## 错误详情与异常追踪\n\n")
        has_errors = False
        for r in results:
            failed_modules = [(mod, r[mod]) for mod in ["norm", "spatial", "generator", "export"] if r[mod]["status"] == "Failed"]
            if failed_modules:
                has_errors = True
                f.write(f"### Dataset: `{r['name']}`\n\n")
                for mod_name, mod_info in failed_modules:
                    f.write(f"- **{mod_name}** error:\n")
                    f.write(f"  ```\n  {mod_info['error']}\n  ```\n")
        
        if not has_errors:
            f.write("> **All datasets passed successfully!** 🚀\n")

if __name__ == "__main__":
    results = test_pipeline()
    generate_md_report(results)
    print("Report written to GTFS_Unit_Test_Report.md")
