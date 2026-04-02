import argparse
import os
import time
from pathlib import Path
import pandas as pd

# Import the decoupled pipeline modules
from gtfs_norm import rawgtfs_from_zip, gtfs_normalize
from gtfs_spatial import ag_ap_generate_reshape
from gtfs_generator import itineraire_generate, course_generate
from gtfs_export import MEF_course, MEF_iti

def main():
    parser = argparse.ArgumentParser(description="Run GTFS Miner pipeline without QGIS.")
    parser.add_argument("--input", required=True, help="Path to the GTFS .zip file or directory containing .txt files.")
    parser.add_argument("--output", default="output", help="Directory to save the processed output CSV files.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)

    if not input_path.exists():
        print(f"Error: Input path '{input_path}' does not exist.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== GTFS Miner Standalone CLI ===")
    print(f"Input:  {input_path}")
    print(f"Output: {output_dir}\n")
    
    start_time = time.time()

    # 1. Load Raw GTFS Data
    print("[1/5] Loading raw GTFS data...")
    if input_path.is_dir():
        raw_dict = {}
        for f in input_path.glob('*.txt'):
            raw_dict[f.stem] = pd.read_csv(f, low_memory=False)
    else:
        raw_dict = rawgtfs_from_zip(input_path)
    
    if not raw_dict:
        print("Error: No GTFS .txt tables found in the input.")
        return
        
    print(f"  -> Loaded tables: {', '.join(raw_dict.keys())}")

    # 2. Normalize Schema
    print("[2/5] Normalizing schema and standardizing formats...")
    normed = gtfs_normalize(raw_dict)
    print(f"  -> Processed {len(normed['stops'])} stops, {len(normed['routes'])} routes, {len(normed['trips'])} trips.")

    # 3. Spatial Processing
    print("[3/5] Generating spatial mappings (AG/AP)...")
    AP, AG, cluster_method = ag_ap_generate_reshape(normed['stops'])
    print(f"  -> Clustering method used: {cluster_method}")
    print(f"  -> Generated {len(AG)} Parent Stations (AG) and {len(AP)} Access Points (AP).")

    # 4. Generate Business Entities
    print("[4/5] Generating itineraries and courses...")
    itineraire = itineraire_generate(normed['stop_times'], AP, normed['trips'])
    courses = course_generate(itineraire)
    print(f"  -> Generated {len(itineraire)} stop time records.")
    print(f"  -> Consolidated into {len(courses)} unique trip courses.")

    # 5. Format & Export
    print(f"[5/5] Formatting and saving results to {output_dir}...")
    mef_courses = MEF_course(courses, normed['trip_id_coor'])
    mef_itineraire = MEF_iti(itineraire, courses)
    
    # Save base entities
    AG.to_csv(output_dir / "AG.csv", index=False, encoding='utf-8-sig')
    AP.to_csv(output_dir / "AP.csv", index=False, encoding='utf-8-sig')
    normed['routes'].to_csv(output_dir / "routes_norm.csv", index=False, encoding='utf-8-sig')
    normed['trips'].to_csv(output_dir / "trips_norm.csv", index=False, encoding='utf-8-sig')
    
    # Save generated entities
    mef_courses.to_csv(output_dir / "courses.csv", index=False, encoding='utf-8-sig')
    mef_itineraire.to_csv(output_dir / "itineraire.csv", index=False, encoding='utf-8-sig')
    
    elapsed = time.time() - start_time
    print(f"\n✅ Processing successfully completed in {elapsed:.2f} seconds.")

if __name__ == "__main__":
    main()
