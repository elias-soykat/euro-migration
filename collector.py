#!/usr/bin/env python3
"""
BMET E-Card Data Collector for 2026 European Countries
Systematically retrieves and validates BMET e-card records from RAIMS (raims.oep.gov.bd).
"""

import os
import sys
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

COUNTRIES = [
    {
        "name": "Portugal",
        "code": "PT",
        "filename": "portugal_2026.json",
        "known_max": 6006573
    },
    {
        "name": "Italy",
        "code": "IT",
        "filename": "italy_2026.json",
        "known_max": 6008235
    },
    {
        "name": "Greece",
        "code": "GR",
        "filename": "greece_2026.json",
        "known_max": 6001531
    },
    {
        "name": "Cyprus",
        "code": "CY",
        "filename": "cyprus_2026.json",
        "known_max": 6002387
    },
    {
        "name": "North Macedonia",
        "code": "MK",
        "filename": "north_macedonia_2026.json",
        "known_max": 6001462
    },
    {
        "name": "Romania",
        "code": "RO",
        "filename": "romania_2026.json",
        "known_max": 6001094
    },
    {
        "name": "Moldova",
        "code": "MD",
        "filename": "moldova_2026.json",
        "known_max": 6000774
    },
    {
        "name": "Malta",
        "code": "MT",
        "filename": "malta_2026.json",
        "known_max": 6000606
    },
    {
        "name": "Slovenia",
        "code": "SI",
        "filename": "slovenia_2026.json",
        "known_max": 6000289
    },
    {
        "name": "Serbia",
        "code": "RS",
        "filename": "serbia_2026.json",
        "known_max": 6002951
    },
    {
        "name": "Bulgaria",
        "code": "BG",
        "filename": "bulgaria_2026.json",
        "known_max": 6000240
    },
    {
        "name": "Bosnia and Herzegovina",
        "code": "BA",
        "filename": "bosnia_and_herzegovina_2026.json",
        "known_max": 6000237
    }
]

WORKSPACE_DIR = "/home/elias/elias/euro-migration"
SUMMARY_FILE = os.path.join(WORKSPACE_DIR, "summary_2026.json")
START_SERIAL = 6000001
MAX_WORKERS = 20
POST_MAX_CHECK_COUNT = 50  # consecutive 302 checks past max confirmed serial
LOOKAHEAD_PROBES = [5, 10, 25, 50, 100, 200, 500]

thread_local = threading.local()

def get_session():
    if not hasattr(thread_local, "session"):
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=5,
            pool_maxsize=5,
            max_retries=requests.adapters.Retry(
                total=5,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504],
                raise_on_status=False
            )
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        })
        thread_local.session = s
    return thread_local.session

def clean_text(text):
    if not text:
        return ""
    return " ".join(text.split())

def parse_card_html(html, url, country, country_code, serial, year):
    soup = BeautifulSoup(html, "html.parser")

    candidate_name = ""
    photo_url = ""
    ec_no = f"{country_code}-I-{year}-{serial}"
    ec_date = ""

    pic_div = soup.find("div", id="pic-wrap")
    if pic_div and pic_div.find("img"):
        photo_url = pic_div.find("img").get("src", "").strip()

    info_board = soup.find("div", id="info-board")
    if info_board:
        p_tags = info_board.find_all("p")
        if len(p_tags) > 0:
            candidate_name = clean_text(p_tags[0].get_text())
        for sp in info_board.find_all("span", class_="card-label"):
            lbl = clean_text(sp.get_text()).rstrip(":").strip()
            nxt = sp.find_next_sibling("span")
            val = clean_text(nxt.get_text()) if nxt else ""
            if lbl == "EC No":
                ec_no = val
            elif lbl == "EC Date":
                ec_date = val

    cl_table = {}
    agency_board = soup.find("div", id="agency-board")
    if agency_board and agency_board.find("table"):
        for tr in agency_board.find("table").find_all("tr"):
            th = tr.find("th")
            td = tr.find("td")
            if th and td:
                cl_table[clean_text(th.get_text()).rstrip(":").strip()] = clean_text(td.get_text())

    section_tables = {}
    wraps = soup.find_all("div", id="wrap")
    for wrap in wraps:
        if wrap.find("div", id="agency-board"):
            continue
        top = wrap.find("div", id="top")
        if not top:
            continue
        title_div = top.find("div", class_="title")
        if not title_div:
            continue
        sec_title = clean_text(title_div.get_text()).lower()

        table = wrap.find("table")
        if table:
            row_dict = {}
            for tr in table.find_all("tr"):
                th = tr.find("th")
                td = tr.find("td")
                if th and td:
                    row_dict[clean_text(th.get_text()).rstrip(":").strip()] = clean_text(td.get_text())

            if "agency" in sec_title:
                section_tables["agency"] = row_dict
            elif "registration" in sec_title:
                section_tables["bmet"] = row_dict
            elif "passports" in sec_title:
                section_tables["passports"] = row_dict
            elif "address" in sec_title:
                section_tables["address"] = row_dict
            elif "emergency" in sec_title:
                section_tables["emergency"] = row_dict

    passports_obj = section_tables.get("passports", {})
    cl_passport = cl_table.get("Passport No", "").strip()
    prev_passports = []
    for k, v in passports_obj.items():
        if k != "Name" and v and v.strip() != cl_passport:
            if v.strip() not in prev_passports:
                prev_passports.append(v.strip())

    bm = section_tables.get("bmet", {})
    ra = section_tables.get("agency", {})
    pa = section_tables.get("address", {})
    ec = section_tables.get("emergency", {})

    record = {
        "country": country,
        "country_code": country_code,
        "year": str(year),
        "serial_number": int(serial),
        "ec_no": ec_no,
        "ec_date": ec_date,
        "verification_url": url,
        "photo_url": photo_url,
        "candidate_name": candidate_name,
        "birth_date": cl_table.get("Birth Date", bm.get("Birth Date", "")).strip(),
        "gender": bm.get("Gender", "").strip(),
        "blood_group": cl_table.get("Blood Group", "").strip(),
        "nid": str(bm.get("NID", "")).strip(),
        "bmet_no": bm.get("BMET No", "").strip(),
        "passport": {
            "passport_no": cl_passport or passports_obj.get("Passport No 1", "").strip(),
            "issue_date": cl_table.get("Passport Issue Date", "").strip(),
            "expire_date": cl_table.get("Passport Expire Date", "").strip(),
            "previous_passports": prev_passports
        },
        "visa": {
            "visa_no": str(cl_table.get("Visa No", "")).strip(),
            "issue_date": cl_table.get("Visa Issue Date", "").strip(),
            "expire_date": cl_table.get("Visa Expire Date", "").strip()
        },
        "employment": {
            "employer": cl_table.get("Employer", "").strip(),
            "referral_no": str(cl_table.get("Referral No", "")).strip()
        },
        "recruiting_agency": {
            "name": ra.get("Name", "").strip(),
            "license_no": str(ra.get("License No", "")).strip(),
            "phone": str(ra.get("Phone", "")).strip()
        },
        "permanent_address": {
            "house_vill_road": pa.get("House/Vill/Road", "").strip(),
            "post_office": pa.get("Post Office", "").strip(),
            "police_station": pa.get("Police Station", "").strip(),
            "upazila": pa.get("Upazila", "").strip(),
            "district": pa.get("District", "").strip(),
            "division": pa.get("Division", "").strip()
        },
        "emergency_contact": {
            "name": ec.get("Name", "").strip(),
            "relation": ec.get("Relation", "").strip(),
            "mobile": str(ec.get("Mobile", "")).strip(),
            "address": ec.get("Address", "").strip()
        }
    }
    return record

def fetch_single_card(country_info, serial):
    code = country_info["code"]
    country = country_info["name"]
    url = f"https://raims.oep.gov.bd/ec-card/verify/{code}-I-2026-{serial}"
    s = get_session()
    s.cookies.clear()

    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            r = s.get(url, allow_redirects=False, timeout=12)
            if r.status_code == 200:
                card_data = parse_card_html(r.text, url, country, code, serial, "2026")
                return {
                    "serial": serial,
                    "status": "valid",
                    "data": card_data,
                    "error": None
                }
            elif r.status_code == 302:
                return {
                    "serial": serial,
                    "status": "invalid",
                    "data": None,
                    "error": None
                }
            elif r.status_code == 404:
                return {
                    "serial": serial,
                    "status": "missing",
                    "data": None,
                    "error": None
                }
            else:
                if attempt == max_attempts:
                    return {
                        "serial": serial,
                        "status": "error",
                        "data": None,
                        "error": f"HTTP {r.status_code}"
                    }
                time.sleep(attempt * 0.5)
        except Exception as e:
            if attempt == max_attempts:
                return {
                    "serial": serial,
                    "status": "error",
                    "data": None,
                    "error": str(e)
                }
            time.sleep(attempt * 0.5)

    return {
        "serial": serial,
        "status": "error",
        "data": None,
        "error": "Exhausted retries"
    }

def update_summary_file(all_summaries):
    ordered_list = []
    for c in COUNTRIES:
        if c["code"] in all_summaries:
            ordered_list.append(all_summaries[c["code"]])

    tmp_file = SUMMARY_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(ordered_list, f, indent=2, ensure_ascii=False)
    os.replace(tmp_file, SUMMARY_FILE)

def process_country(country_info, all_summaries):
    country_name = country_info["name"]
    code = country_info["code"]
    filename = country_info["filename"]
    known_max = country_info.get("known_max", START_SERIAL)
    out_path = os.path.join(WORKSPACE_DIR, filename)

    print(f"\n=======================================================", flush=True)
    print(f"Starting collection for: {country_name} ({code})", flush=True)
    print(f"Start serial: {START_SERIAL} | Expected max approx: {known_max}", flush=True)
    print(f"Target file: {filename}", flush=True)
    print(f"=======================================================", flush=True)

    valid_records = []
    invalid_serials = []
    error_serials = []
    highest_confirmed = None
    last_card_details = None

    batch_size = 200
    current_start = START_SERIAL
    target_end = known_max + POST_MAX_CHECK_COUNT

    consecutive_invalid_past_highest = 0
    checked_count = 0

    while True:
        batch_end = min(current_start + batch_size - 1, target_end)
        serials_to_fetch = list(range(current_start, batch_end + 1))
        
        batch_results = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_sn = {
                executor.submit(fetch_single_card, country_info, sn): sn 
                for sn in serials_to_fetch
            }
            for future in as_completed(future_to_sn):
                batch_results.append(future.result())

        batch_results.sort(key=lambda x: x["serial"])

        for res in batch_results:
            sn = res["serial"]
            st = res["status"]
            checked_count += 1

            if st == "valid":
                valid_records.append(res["data"])
                if highest_confirmed is None or sn > highest_confirmed:
                    highest_confirmed = sn
                    last_card_details = {
                        "ec_no": res["data"].get("ec_no"),
                        "ec_date": res["data"].get("ec_date"),
                        "candidate_name": res["data"].get("candidate_name")
                    }
                consecutive_invalid_past_highest = 0
            elif st in ("invalid", "missing"):
                invalid_serials.append(sn)
                if highest_confirmed is not None and sn > highest_confirmed:
                    consecutive_invalid_past_highest += 1
            else:
                error_serials.append({"serial": sn, "error": res["error"]})
                if highest_confirmed is not None and sn > highest_confirmed:
                    consecutive_invalid_past_highest += 1

        print(f"[{code}] Checked up to {batch_end} | Valid: {len(valid_records)} | Highest: {highest_confirmed} | Invalids: {len(invalid_serials)}", flush=True)

        if batch_end >= target_end and consecutive_invalid_past_highest >= POST_MAX_CHECK_COUNT:
            break

        if highest_confirmed and highest_confirmed + POST_MAX_CHECK_COUNT > target_end:
            target_end = highest_confirmed + POST_MAX_CHECK_COUNT

        current_start = batch_end + 1
        if current_start > target_end:
            break

    # Look-ahead boundary verification
    print(f"[{code}] Performing look-ahead boundary verification...", flush=True)
    probe_base = highest_confirmed if highest_confirmed else START_SERIAL
    probe_serials = [probe_base + p for p in LOOKAHEAD_PROBES]
    probe_results = {}
    last_confirmed = True

    with ThreadPoolExecutor(max_workers=min(len(probe_serials), MAX_WORKERS)) as executor:
        future_to_p = {
            executor.submit(fetch_single_card, country_info, p): p 
            for p in probe_serials
        }
        for future in as_completed(future_to_p):
            res = future.result()
            probe_results[res["serial"]] = res["status"]
            checked_count += 1
            if res["status"] == "valid":
                last_confirmed = False
                valid_records.append(res["data"])
                if res["serial"] > highest_confirmed:
                    highest_confirmed = res["serial"]
                    last_card_details = {
                        "ec_no": res["data"].get("ec_no"),
                        "ec_date": res["data"].get("ec_date"),
                        "candidate_name": res["data"].get("candidate_name")
                    }
            elif res["status"] in ("invalid", "missing"):
                invalid_serials.append(res["serial"])

    print(f"[{code}] Look-ahead probe results: {probe_results}", flush=True)
    print(f"[{code}] Conclusive end confirmed: {last_confirmed}", flush=True)

    seen_sn = set()
    unique_valid_records = []
    for r in sorted(valid_records, key=lambda x: x["serial_number"]):
        if r["serial_number"] not in seen_sn:
            seen_sn.add(r["serial_number"])
            unique_valid_records.append(r)

    tmp_out = out_path + ".tmp"
    with open(tmp_out, "w", encoding="utf-8") as f:
        json.dump(unique_valid_records, f, indent=2, ensure_ascii=False)
    os.replace(tmp_out, out_path)
    print(f"[{code}] Saved {len(unique_valid_records)} records to {filename}", flush=True)

    internal_gaps = [
        sn for sn in invalid_serials 
        if highest_confirmed and START_SERIAL <= sn < highest_confirmed
    ]

    notes = []
    if internal_gaps:
        notes.append(f"Internal unissued/missing serials before highest ({len(internal_gaps)}): {internal_gaps[:10]}{'...' if len(internal_gaps) > 10 else ''}")
    else:
        notes.append("No internal serial gaps; perfectly contiguous up to highest confirmed serial.")
    if error_serials:
        notes.append(f"Network retries/errors encountered: {len(error_serials)}")

    country_summary = {
        "country_name": country_name,
        "country_code": code,
        "output_file": filename,
        "starting_serial_number": START_SERIAL,
        "highest_confirmed_serial_number": highest_confirmed,
        "total_serial_numbers_checked": checked_count,
        "total_valid_records_found": len(unique_valid_records),
        "total_invalid_or_missing_records": len(invalid_serials),
        "last_available_record_confirmed": last_confirmed,
        "errors_gaps_or_limitations": "; ".join(notes),
        "confirmation_evidence": {
            "consecutive_302_checks_past_highest": consecutive_invalid_past_highest,
            "lookahead_probe_serials": probe_serials,
            "lookahead_probe_results": probe_results,
            "highest_record_issuance_date": last_card_details.get("ec_date") if last_card_details else None
        },
        "last_record_details": last_card_details
    }

    all_summaries[code] = country_summary
    update_summary_file(all_summaries)

    print(f"[{code}] Finished successfully! Highest: {highest_confirmed} | Valid count: {len(unique_valid_records)}", flush=True)
    return country_summary

def load_existing_summaries():
    all_summaries = {}
    if os.path.exists(SUMMARY_FILE):
        try:
            with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        all_summaries[item["country_code"]] = item
                elif isinstance(data, dict):
                    all_summaries = data
        except Exception:
            all_summaries = {}
    return all_summaries

def main():
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    all_summaries = load_existing_summaries()

    start_time = time.time()
    for country_info in COUNTRIES:
        code = country_info["code"]
        out_file = os.path.join(WORKSPACE_DIR, country_info["filename"])
        
        # Check if already completed and file exists and has records
        if code in all_summaries and os.path.exists(out_file) and all_summaries[code].get("last_available_record_confirmed"):
            valid_cnt = all_summaries[code].get("total_valid_records_found", all_summaries[code].get("total_valid_records", 0))
            print(f"Skipping {country_info['name']} ({code}) - already completed with {valid_cnt} records.", flush=True)
            continue

        process_country(country_info, all_summaries)

    elapsed = round(time.time() - start_time, 2)
    print(f"\n=======================================================", flush=True)
    print(f"ALL 12 COUNTRIES COMPLETED IN {elapsed}s!", flush=True)
    print(f"Summary written to {SUMMARY_FILE}", flush=True)
    print(f"=======================================================", flush=True)

if __name__ == "__main__":
    main()
