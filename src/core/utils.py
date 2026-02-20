import re
import pandas as pd
from loguru import logger

def compare_to_ad(df: pd.DataFrame, ad_file_dict: dict) -> pd.DataFrame:

    ad_columns = list(ad_file_dict.keys())
    ad_rows = []

    for _, item in df.iterrows():
        model = str(item["aircraft_model"])
        msn = int(item["msn"])

        raw_mod = item["modifications_applied"]
        if pd.isna(raw_mod) or str(raw_mod).strip().lower() in ("none", "n/a", ""):
            mods_applied = []
        else:
            mods_applied = [m.strip() for m in str(raw_mod).split(",")]

        logger.info(
            f"🔎 Checking AD status — model: {model}, MSN: {msn}, mods: {mods_applied}"
        )

        ad_status_rows = []

        for ad in ad_columns:
            logger.debug(f"   📋 Checking against: {ad}")
            ad_data = ad_file_dict[ad]

            # --- Model check ---
            model_status = any(model in m for m in ad_data["models"])
            if not model_status:
                ad_status_rows.append("❌ Not applicable")
                continue

            # --- MSN check ---
            msn_constraints = ad_data.get("msn_constraints") or []

            if not msn_constraints:
                msn_status = True
            else:
                msn_status = False
                for msn_constraint in msn_constraints:
                    all_msn = msn_constraint.get("all")
                    range_data = msn_constraint.get("range")
                    specific = msn_constraint.get("specific_msns")
                    excluded = msn_constraint.get("excluded", False)

                    matched = False

                    if all_msn:
                        matched = True
                    elif range_data:
                        start = range_data.get("start")
                        end = range_data.get("end")
                        incl_start = range_data.get("inclusive_start", True)
                        incl_end = range_data.get("inclusive_end", True)
                        lower_ok = (msn >= start) if incl_start else (msn > start)
                        upper_ok = (msn <= end) if incl_end else (msn < end)
                        matched = lower_ok and upper_ok
                    elif specific:
                        matched = msn in specific

                    if matched:
                        msn_status = not excluded
                        break

            if not msn_status:
                ad_status_rows.append("❌ Not applicable")
                continue

            # --- Modification / SB exclusion check ---
            if not mods_applied:
                ad_status_rows.append("✅ Affected")
                continue

            excluded_by_mod = False

            for mod_applied in mods_applied:
                if "mod" in mod_applied.lower():
                    mod_constraints = ad_data.get("modification_constraints") or []
                    for mod_constraint in mod_constraints:
                        mod_id = mod_constraint.get("modification_id", "")
                        is_excluded = mod_constraint.get("excluded", False)
                        if re.search(r"\b" + re.escape(mod_id) + r"\b", mod_applied):
                            if is_excluded:
                                excluded_by_mod = True
                            break
                else:
                    sb_constraints = ad_data.get("sb_constraints") or []
                    for sb_constraint in sb_constraints:
                        sb_id = sb_constraint.get("sb_identifier", "")
                        is_excluded = sb_constraint.get("excluded", False)
                        if re.search(r"\b" + re.escape(sb_id) + r"\b", mod_applied):
                            if is_excluded:
                                excluded_by_mod = True
                            break

                if excluded_by_mod:
                    break

            if excluded_by_mod:
                ad_status_rows.append("❌ Not Affected")
            else:
                ad_status_rows.append("✅ Affected")

        ad_rows.append(ad_status_rows)

    ad_df = pd.DataFrame(ad_rows, columns=ad_columns)
    combined_df = pd.concat([df, ad_df], axis=1)
    
    return combined_df