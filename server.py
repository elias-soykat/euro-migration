#!/usr/bin/env python3
"""
BMET E-Card Directory Server
Backend API and Static Server for the European Migration BMET Clearance Cards Directory.
"""

import os
import sys
import json
import time
import datetime
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import requests
from bs4 import BeautifulSoup

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(WORKSPACE_DIR, "public")
SUMMARY_FILE = os.path.join(WORKSPACE_DIR, "summary_2026.json")

# In-memory dataset cache: code -> {"mtime": float, "data": list}
DATASET_CACHE = {}

COUNTRY_META = {
    "PT": {"name": "Portugal", "flag": "🇵🇹", "file": "portugal_2026.json"},
    "IT": {"name": "Italy", "flag": "🇮🇹", "file": "italy_2026.json"},
    "GR": {"name": "Greece", "flag": "🇬🇷", "file": "greece_2026.json"},
    "CY": {"name": "Cyprus", "flag": "🇨🇾", "file": "cyprus_2026.json"},
    "MK": {"name": "North Macedonia", "flag": "🇲🇰", "file": "north_macedonia_2026.json"},
    "RO": {"name": "Romania", "flag": "🇷🇴", "file": "romania_2026.json"},
    "MD": {"name": "Moldova", "flag": "🇲🇩", "file": "moldova_2026.json"},
    "MT": {"name": "Malta", "flag": "🇲🇹", "file": "malta_2026.json"},
    "SI": {"name": "Slovenia", "flag": "🇸🇮", "file": "slovenia_2026.json"},
    "RS": {"name": "Serbia", "flag": "🇷🇸", "file": "serbia_2026.json"},
    "BG": {"name": "Bulgaria", "flag": "🇧🇬", "file": "bulgaria_2026.json"},
    "BA": {"name": "Bosnia and Herzegovina", "flag": "🇧🇦", "file": "bosnia_and_herzegovina_2026.json"}
}

def clean_text(text):
    if not text:
        return ""
    return " ".join(text.split())

def parse_card_html(html, url, country, country_code, serial, year):
    soup = BeautifulSoup(html, "html.parser")
    
    # Extract candidate name and photo
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

    # Tables extraction
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

    # Extract historical previous passports if any
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

def get_country_records(code):
    code = code.upper()
    if code not in COUNTRY_META:
        return []

    filepath = os.path.join(WORKSPACE_DIR, COUNTRY_META[code]["file"])
    if not os.path.exists(filepath):
        return []

    mtime = os.path.getmtime(filepath)
    if code in DATASET_CACHE and DATASET_CACHE[code]["mtime"] == mtime:
        return DATASET_CACHE[code]["data"]

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            DATASET_CACHE[code] = {"mtime": mtime, "data": data}
            return data
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return []

def get_summary_data():
    if os.path.exists(SUMMARY_FILE):
        try:
            with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading summary file: {e}")
    return []

def update_summary_entry(code, highest_sn, valid_count, last_record, check_time_str):
    summary_list = get_summary_data()
    updated = False
    for item in summary_list:
        if item.get("country_code") == code:
            item["highest_confirmed_serial_number"] = highest_sn
            item["total_valid_records_found"] = valid_count
            item["last_record_details"] = {
                "ec_no": last_record.get("ec_no"),
                "ec_date": last_record.get("ec_date"),
                "candidate_name": last_record.get("candidate_name")
            }
            item["last_checked_timestamp"] = check_time_str
            updated = True
            break
    
    if updated:
        tmp = SUMMARY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(summary_list, f, indent=2, ensure_ascii=False)
        os.replace(tmp, SUMMARY_FILE)

def parse_ec_date(date_str):
    if not date_str:
        return datetime.date.min
    try:
        # Expected format like "03/Jan/2026" or "2026-01-03"
        if "/" in date_str:
            return datetime.datetime.strptime(date_str, "%d/%b/%Y").date()
        elif "-" in date_str:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        pass
    return datetime.date.min

class DirectoryAPIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def send_json(self, data, status_code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if path == "/api/countries":
            self.handle_get_countries()
        elif path == "/api/cards":
            self.handle_get_cards(params)
        elif path == "/api/card":
            self.handle_get_card(params)
        elif path == "/api/stats":
            self.handle_get_stats()
        else:
            # Serve static files from public/
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/check-new-cards":
            self.handle_check_new_cards()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_get_countries(self):
        summary_list = get_summary_data()
        summary_map = {item.get("country_code"): item for item in summary_list}

        countries_resp = []
        for code, meta in COUNTRY_META.items():
            s_item = summary_map.get(code, {})
            # Verify actual loaded records count
            records = get_country_records(code)
            valid_count = len(records)
            highest_sn = max([r["serial_number"] for r in records]) if records else s_item.get("highest_confirmed_serial_number", 6000001)
            last_card = records[-1] if records else {}

            countries_resp.append({
                "country_name": meta["name"],
                "country_code": code,
                "flag": meta["flag"],
                "output_file": meta["file"],
                "total_valid_records": valid_count,
                "highest_confirmed_serial": highest_sn,
                "starting_serial": s_item.get("starting_serial_number", 6000001),
                "last_available_record_confirmed": s_item.get("last_available_record_confirmed", True),
                "last_record_details": {
                    "ec_no": last_card.get("ec_no", s_item.get("last_record_details", {}).get("ec_no", "")),
                    "ec_date": last_card.get("ec_date", s_item.get("last_record_details", {}).get("ec_date", "")),
                    "candidate_name": last_card.get("candidate_name", s_item.get("last_record_details", {}).get("candidate_name", ""))
                },
                "last_checked_timestamp": s_item.get("last_checked_timestamp", None)
            })

        self.send_json({"countries": countries_resp})

    def handle_get_cards(self, params):
        code = params.get("country", ["PT"])[0].upper()
        if code not in COUNTRY_META:
            self.send_json({"error": f"Invalid country code: {code}"}, status_code=400)
            return

        records = get_country_records(code)

        search = params.get("search", [""])[0].strip().lower()
        field_filter = params.get("field", ["all"])[0].strip().lower()
        sort_by = params.get("sort", ["serial_desc"])[0].strip()

        try:
            page = max(1, int(params.get("page", ["1"])[0]))
        except ValueError:
            page = 1

        try:
            limit = min(200, max(5, int(params.get("limit", ["25"])[0])))
        except ValueError:
            limit = 25

        # Filtering
        if search:
            filtered = []
            for r in records:
                matched = False
                name = r.get("candidate_name", "").lower()
                sn_str = str(r.get("serial_number", ""))
                ec_no = r.get("ec_no", "").lower()
                clearance = r.get("emigration_clearance", {})
                pass_no = (r.get("passport", {}).get("passport_no") or clearance.get("Passport No", "")).lower()
                visa_no = (r.get("visa", {}).get("visa_no") or clearance.get("Visa No", "")).lower()
                employer = (r.get("employment", {}).get("employer") or clearance.get("Employer", "")).lower()
                agency_obj = r.get("recruiting_agency", {})
                agency = (agency_obj.get("name") or agency_obj.get("Name", "")).lower()
                agency_lic = (agency_obj.get("license_no") or agency_obj.get("License No", "")).lower()
                bmet_no = (r.get("bmet_no") or r.get("bmet_registration", {}).get("BMET No", "")).lower()
                addr_obj = r.get("permanent_address", {})
                district = (addr_obj.get("district") or addr_obj.get("District", "")).lower()

                if field_filter == "name":
                    matched = search in name
                elif field_filter == "passport":
                    matched = search in pass_no
                elif field_filter == "serial":
                    matched = search == sn_str or search in ec_no
                elif field_filter == "employer":
                    matched = search in employer
                elif field_filter == "agency":
                    matched = search in agency or search in agency_lic
                elif field_filter == "district":
                    matched = search in district
                else:
                    # All fields
                    matched = (
                        search in name or
                        search in pass_no or
                        search in sn_str or
                        search in ec_no or
                        search in visa_no or
                        search in employer or
                        search in agency or
                        search in agency_lic or
                        search in bmet_no or
                        search in district
                    )
                if matched:
                    filtered.append(r)
        else:
            filtered = records

        # Sorting
        if sort_by == "serial_asc":
            filtered.sort(key=lambda x: x.get("serial_number", 0))
        elif sort_by == "name_asc":
            filtered.sort(key=lambda x: x.get("candidate_name", "").lower())
        elif sort_by == "name_desc":
            filtered.sort(key=lambda x: x.get("candidate_name", "").lower(), reverse=True)
        elif sort_by == "date_desc":
            filtered.sort(key=lambda x: parse_ec_date(x.get("ec_date")), reverse=True)
        elif sort_by == "date_asc":
            filtered.sort(key=lambda x: parse_ec_date(x.get("ec_date")))
        else:
            # Default: serial_desc
            filtered.sort(key=lambda x: x.get("serial_number", 0), reverse=True)

        total_matching = len(filtered)
        total_pages = max(1, (total_matching + limit - 1) // limit)
        if page > total_pages:
            page = total_pages

        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_cards = filtered[start_idx:end_idx]

        self.send_json({
            "country_name": COUNTRY_META[code]["name"],
            "country_code": code,
            "flag": COUNTRY_META[code]["flag"],
            "total_records": len(records),
            "total_matching": total_matching,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "cards": paginated_cards
        })

    def handle_get_card(self, params):
        code = params.get("country", ["PT"])[0].upper()
        serial_str = params.get("serial", [""])[0].strip()

        if code not in COUNTRY_META or not serial_str:
            self.send_json({"error": "Invalid country code or serial number"}, status_code=400)
            return

        try:
            target_sn = int(serial_str)
        except ValueError:
            self.send_json({"error": "Invalid serial format"}, status_code=400)
            return

        records = get_country_records(code)
        for r in records:
            if r.get("serial_number") == target_sn:
                self.send_json({"card": r})
                return

        self.send_json({"error": f"Card {code}-{target_sn} not found"}, status_code=404)

    def handle_get_stats(self):
        summary_list = get_summary_data()
        total_valid = 0
        countries_stats = []
        for s in summary_list:
            code = s.get("country_code")
            meta = COUNTRY_META.get(code, {})
            records = get_country_records(code)
            count = len(records)
            total_valid += count
            countries_stats.append({
                "country_name": s.get("country_name"),
                "country_code": code,
                "flag": meta.get("flag", "🌐"),
                "total_valid_records": count,
                "highest_serial": max([r["serial_number"] for r in records]) if records else 6000001
            })

        self.send_json({
            "total_countries": len(countries_stats),
            "total_valid_cards_all": total_valid,
            "countries": countries_stats
        })

    def handle_check_new_cards(self):
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            self.send_json({"error": "Empty request body"}, status_code=400)
            return

        try:
            body = json.loads(self.rfile.read(content_len).decode("utf-8"))
        except Exception as e:
            self.send_json({"error": f"Invalid JSON payload: {e}"}, status_code=400)
            return

        code = body.get("country_code", "").upper().strip()
        if code not in COUNTRY_META:
            self.send_json({"error": f"Unknown country code '{code}'"}, status_code=400)
            return

        country_name = COUNTRY_META[code]["name"]
        filename = COUNTRY_META[code]["file"]
        filepath = os.path.join(WORKSPACE_DIR, filename)

        records = get_country_records(code)
        current_highest = max([r["serial_number"] for r in records]) if records else 6000000
        start_probe_sn = current_highest + 1
        check_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"[{code}] Checking for new cards starting after {current_highest} at {check_time_str}...")

        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=2)
        s.mount("https://", adapter)
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BMET-Checker/2026",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        })

        new_cards = []
        curr_sn = start_probe_sn
        consecutive_misses = 0
        max_miss_limit = 5  # Stop probing once 5 consecutive serial numbers are 302
        errors_encountered = []

        # We probe sequentially past current_highest
        while consecutive_misses < max_miss_limit:
            url = f"https://raims.oep.gov.bd/ec-card/verify/{code}-I-2026-{curr_sn}"
            try:
                s.cookies.clear()
                r = s.get(url, allow_redirects=False, timeout=8)
                if r.status_code == 200:
                    card_data = parse_card_html(r.text, url, country_name, code, curr_sn, "2026")
                    new_cards.append(card_data)
                    consecutive_misses = 0
                    print(f"[{code}] Found new valid card: {curr_sn} ({card_data.get('candidate_name')})")
                elif r.status_code == 302:
                    consecutive_misses += 1
                else:
                    errors_encountered.append(f"SN {curr_sn}: HTTP {r.status_code}")
                    consecutive_misses += 1
            except Exception as e:
                errors_encountered.append(f"SN {curr_sn}: {str(e)}")
                consecutive_misses += 1

            curr_sn += 1

        # Double check look-ahead probes if none found immediately
        if not new_cards:
            lookahead = [current_highest + 5, current_highest + 15, current_highest + 30]
            for p_sn in lookahead:
                try:
                    s.cookies.clear()
                    r = s.get(f"https://raims.oep.gov.bd/ec-card/verify/{code}-I-2026-{p_sn}", allow_redirects=False, timeout=6)
                    if r.status_code == 200:
                        card_data = parse_card_html(r.text, f"https://raims.oep.gov.bd/ec-card/verify/{code}-I-2026-{p_sn}", country_name, code, p_sn, "2026")
                        new_cards.append(card_data)
                        print(f"[{code}] Found look-ahead card: {p_sn}")
                except Exception as e:
                    pass

        # If new cards found, update disk JSON atomically
        if new_cards:
            # Merge with existing records, deduplicate
            existing_sn_map = {r["serial_number"]: r for r in records}
            for nc in new_cards:
                existing_sn_map[nc["serial_number"]] = nc

            merged_records = sorted(existing_sn_map.values(), key=lambda x: x["serial_number"])

            tmp_filepath = filepath + ".tmp"
            with open(tmp_filepath, "w", encoding="utf-8") as f:
                json.dump(merged_records, f, indent=2, ensure_ascii=False)
            os.replace(tmp_filepath, filepath)

            # Invalidate cache
            if code in DATASET_CACHE:
                del DATASET_CACHE[code]

            updated_highest = max(existing_sn_map.keys())
            last_rec = merged_records[-1]

            # Update summary_2026.json
            update_summary_entry(code, updated_highest, len(merged_records), last_rec, check_time_str)

            self.send_json({
                "status": "success",
                "country_code": code,
                "country_name": country_name,
                "new_cards_count": len(new_cards),
                "new_cards": new_cards,
                "previous_highest_serial": current_highest,
                "latest_serial_number": updated_highest,
                "total_valid_records": len(merged_records),
                "check_time": check_time_str,
                "message": f"Successfully fetched and saved {len(new_cards)} newly issued card(s) for {country_name}!",
                "errors": errors_encountered if errors_encountered else None
            })
        else:
            # Update check timestamp in summary even if no cards
            last_rec = records[-1] if records else {}
            update_summary_entry(code, current_highest, len(records), last_rec, check_time_str)

            self.send_json({
                "status": "success",
                "country_code": code,
                "country_name": country_name,
                "new_cards_count": 0,
                "new_cards": [],
                "previous_highest_serial": current_highest,
                "latest_serial_number": current_highest,
                "total_valid_records": len(records),
                "check_time": check_time_str,
                "message": "No new BMET clearance cards issued for this country.",
                "errors": errors_encountered if errors_encountered else None
            })

def run_server(port=8000):
    server_address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(server_address, DirectoryAPIHandler)
    print(f"BMET Directory Server running at http://localhost:{port}/", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)
