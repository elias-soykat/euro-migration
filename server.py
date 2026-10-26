#!/usr/bin/env python3
"""
BMET E-Card Directory Server
Backend API and Static Server for the European Migration BMET Clearance Cards Directory.
Fully year-independent and future-proof (supporting 2026, 2027, 2028, and beyond).
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

# Country definitions with ISO codes, display names, flags, and file slug prefixes
COUNTRY_META = {
    "PT": {"name": "Portugal", "flag": "🇵🇹", "slug": "portugal"},
    "IT": {"name": "Italy", "flag": "🇮🇹", "slug": "italy"},
    "GR": {"name": "Greece", "flag": "🇬🇷", "slug": "greece"},
    "CY": {"name": "Cyprus", "flag": "🇨🇾", "slug": "cyprus"},
    "MK": {"name": "North Macedonia", "flag": "🇲🇰", "slug": "north_macedonia"},
    "RO": {"name": "Romania", "flag": "🇷🇴", "slug": "romania"},
    "MD": {"name": "Moldova", "flag": "🇲🇩", "slug": "moldova"},
    "MT": {"name": "Malta", "flag": "🇲🇹", "slug": "malta"},
    "SI": {"name": "Slovenia", "flag": "🇸🇮", "slug": "slovenia"},
    "RS": {"name": "Serbia", "flag": "🇷🇸", "slug": "serbia"},
    "BG": {"name": "Bulgaria", "flag": "🇧🇬", "slug": "bulgaria"},
    "BA": {"name": "Bosnia and Herzegovina", "flag": "🇧🇦", "slug": "bosnia_and_herzegovina"}
}

# In-memory dataset cache: (code, year) -> {"mtime": float, "data": list}
DATASET_CACHE = {}

def clean_text(text):
    if not text:
        return ""
    return " ".join(text.split())

def discover_years():
    """
    Dynamically discover all years present in the workspace dataset files
    matching <country_slug>_<year>.json or summary_<year>.json,
    and always include the current calendar year.
    Returns a sorted list of unique year strings, e.g. ['2026', '2027'].
    """
    years = set()
    try:
        for fname in os.listdir(WORKSPACE_DIR):
            if fname.endswith(".json"):
                base = fname[:-5]
                parts = base.rsplit("_", 1)
                if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 4:
                    years.add(parts[1])
    except Exception as e:
        print(f"Error scanning workspace years: {e}")

    curr_year = str(datetime.datetime.now().year)
    years.add(curr_year)
    return sorted(list(years))

def get_country_filepath(code, year):
    meta = COUNTRY_META.get(code.upper())
    if not meta:
        return None
    return os.path.join(WORKSPACE_DIR, f"{meta['slug']}_{year}.json")

def get_summary_filepath(year):
    return os.path.join(WORKSPACE_DIR, f"summary_{year}.json")

def get_record_year(r, default_year=""):
    if r.get("year"):
        return str(r["year"])
    ec = r.get("ec_no", "")
    parts = ec.split("-")
    if len(parts) >= 3 and parts[2].isdigit():
        return parts[2]
    url = r.get("verification_url", "")
    if url:
        u_parts = url.split("/")[-1].split("-")
        if len(u_parts) >= 3 and u_parts[2].isdigit():
            return u_parts[2]
    return str(default_year)

def parse_card_html(html, url, country, country_code, serial, year):
    soup = BeautifulSoup(html, "html.parser")
    
    candidate_name = ""
    ec_no = f"{country_code}-I-{year}-{serial}"
    ec_date = ""

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

    ra = section_tables.get("agency", {})

    record = {
        "serial_number": int(serial),
        "ec_no": ec_no,
        "ec_date": ec_date,
        "verification_url": url,
        "candidate_name": candidate_name
    }

    employer = cl_table.get("Employer", "").strip()
    if employer:
        record["employment"] = {
            "employer": employer
        }

    agency = {}
    ra_name = ra.get("Name", "").strip()
    ra_lic = str(ra.get("License No", "")).strip()
    ra_phone = str(ra.get("Phone", "")).strip()
    if ra_name:
        agency["name"] = ra_name
    if ra_lic:
        agency["license_no"] = ra_lic
    if ra_phone:
        agency["phone"] = ra_phone

    if agency:
        record["recruiting_agency"] = agency

    return record

def get_country_records_for_year(code, year):
    code = code.upper()
    filepath = get_country_filepath(code, year)
    if not filepath or not os.path.exists(filepath):
        return []

    mtime = os.path.getmtime(filepath)
    cache_key = (code, str(year))
    if cache_key in DATASET_CACHE and DATASET_CACHE[cache_key]["mtime"] == mtime:
        return DATASET_CACHE[cache_key]["data"]

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            DATASET_CACHE[cache_key] = {"mtime": mtime, "data": data}
            return data
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return []

def get_country_records(code, year=None):
    code = code.upper()
    if year and str(year).lower() != "all":
        return get_country_records_for_year(code, str(year))

    # All years: combine and deduplicate across all discovered years
    all_years = discover_years()
    combined = []
    seen = set()
    for y in all_years:
        recs = get_country_records_for_year(code, y)
        for r in recs:
            r_year = get_record_year(r, y)
            r_sn = r.get("serial_number")
            key = (r_year, r_sn)
            if key not in seen:
                seen.add(key)
                combined.append(r)
    return combined

def get_summary_data(year=None):
    if year and str(year).lower() != "all":
        sum_path = get_summary_filepath(year)
        if os.path.exists(sum_path):
            try:
                with open(sum_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading summary for {year}: {e}")
        return []

    # All years: load every summary_<year>.json that exists
    all_years = discover_years()
    merged = []
    for y in all_years:
        sum_path = get_summary_filepath(y)
        if os.path.exists(sum_path):
            try:
                with open(sum_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        item["year"] = y
                        merged.append(item)
            except Exception as e:
                print(f"Error reading {sum_path}: {e}")
    return merged

def update_summary_entry(code, year, highest_sn, valid_count, last_record, check_time_str):
    year_str = str(year)
    sum_path = get_summary_filepath(year_str)
    summary_list = []
    if os.path.exists(sum_path):
        try:
            with open(sum_path, "r", encoding="utf-8") as f:
                summary_list = json.load(f)
        except Exception as e:
            print(f"Error reading {sum_path}: {e}")

    meta = COUNTRY_META.get(code, {})
    country_name = meta.get("name", code)
    slug = meta.get("slug", code.lower())

    updated = False
    for item in summary_list:
        if item.get("country_code") == code:
            item["highest_confirmed_serial_number"] = highest_sn
            item["total_valid_records_found"] = valid_count
            item["output_file"] = f"{slug}_{year_str}.json"
            item["last_record_details"] = {
                "ec_no": last_record.get("ec_no", f"{code}-I-{year_str}-{highest_sn}"),
                "ec_date": last_record.get("ec_date", ""),
                "candidate_name": last_record.get("candidate_name", "")
            }
            item["last_checked_timestamp"] = check_time_str
            updated = True
            break

    if not updated:
        summary_list.append({
            "country_name": country_name,
            "country_code": code,
            "output_file": f"{slug}_{year_str}.json",
            "starting_serial_number": 6000001,
            "highest_confirmed_serial_number": highest_sn,
            "total_serial_numbers_checked": valid_count,
            "total_valid_records_found": valid_count,
            "total_invalid_or_missing_records": 0,
            "last_available_record_confirmed": True,
            "errors_gaps_or_limitations": "Contiguous records from initial serial.",
            "confirmation_evidence": {},
            "last_record_details": {
                "ec_no": last_record.get("ec_no", f"{code}-I-{year_str}-{highest_sn}"),
                "ec_date": last_record.get("ec_date", ""),
                "candidate_name": last_record.get("candidate_name", "")
            },
            "last_checked_timestamp": check_time_str
        })

    tmp = sum_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(summary_list, f, indent=2, ensure_ascii=False)
    os.replace(tmp, sum_path)

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

        if path == "/api/years":
            self.handle_get_years()
        elif path == "/api/countries":
            self.handle_get_countries(params)
        elif path == "/api/cards":
            self.handle_get_cards(params)
        elif path == "/api/card":
            self.handle_get_card(params)
        elif path == "/api/stats":
            self.handle_get_stats(params)
        else:
            # Serve static files from public/
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/check-new-cards":
            self.handle_check_new_cards()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_get_years(self):
        years = discover_years()
        curr_year = str(datetime.datetime.now().year)
        self.send_json({
            "available_years": years,
            "current_year": curr_year
        })

    def handle_get_countries(self, params):
        year_filter = params.get("year", ["all"])[0].strip()
        available_years = discover_years()
        curr_year = str(datetime.datetime.now().year)

        countries_resp = []
        for code, meta in COUNTRY_META.items():
            if year_filter and year_filter.lower() != "all":
                # Single year view
                records = get_country_records_for_year(code, year_filter)
                valid_count = len(records)
                highest_sn = max([r["serial_number"] for r in records]) if records else 6000001
                last_card = records[-1] if records else {}
                countries_resp.append({
                    "country_name": meta["name"],
                    "country_code": code,
                    "flag": meta["flag"],
                    "year": year_filter,
                    "output_file": f"{meta['slug']}_{year_filter}.json",
                    "total_valid_records": valid_count,
                    "highest_confirmed_serial": highest_sn,
                    "starting_serial": 6000001,
                    "last_available_record_confirmed": True,
                    "last_record_details": {
                        "ec_no": last_card.get("ec_no", ""),
                        "ec_date": last_card.get("ec_date", ""),
                        "candidate_name": last_card.get("candidate_name", "")
                    },
                    "last_checked_timestamp": None
                })
            else:
                # All years aggregated view
                total_count = 0
                years_breakdown = {}
                highest_sn = 6000001
                all_records = []
                for y in available_years:
                    y_recs = get_country_records_for_year(code, y)
                    count_y = len(y_recs)
                    total_count += count_y
                    years_breakdown[y] = count_y
                    if y_recs:
                        max_y_sn = max(r["serial_number"] for r in y_recs)
                        if max_y_sn > highest_sn:
                            highest_sn = max_y_sn
                        all_records.extend(y_recs)

                last_card = all_records[-1] if all_records else {}
                countries_resp.append({
                    "country_name": meta["name"],
                    "country_code": code,
                    "flag": meta["flag"],
                    "year": "all",
                    "output_file": f"{meta['slug']}_{curr_year}.json",
                    "total_valid_records": total_count,
                    "highest_confirmed_serial": highest_sn,
                    "starting_serial": 6000001,
                    "years_breakdown": years_breakdown,
                    "last_available_record_confirmed": True,
                    "last_record_details": {
                        "ec_no": last_card.get("ec_no", ""),
                        "ec_date": last_card.get("ec_date", ""),
                        "candidate_name": last_card.get("candidate_name", "")
                    },
                    "last_checked_timestamp": None
                })

        self.send_json({
            "selected_year": year_filter,
            "available_years": available_years,
            "current_year": curr_year,
            "countries": countries_resp
        })

    def handle_get_cards(self, params):
        code = params.get("country", ["PT"])[0].upper()
        if code not in COUNTRY_META:
            self.send_json({"error": f"Invalid country code: {code}"}, status_code=400)
            return

        year_param = params.get("year", ["all"])[0].strip()
        records = get_country_records(code, year_param)

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
                r_year = get_record_year(r, "")
                ec_no = r.get("ec_no", "").lower()
                employer = (r.get("employment", {}).get("employer") or r.get("employer", "")).lower()
                agency_obj = r.get("recruiting_agency", {})
                agency = (agency_obj.get("name") or "").lower()
                agency_lic = (agency_obj.get("license_no") or "").lower()
                agency_phone = (agency_obj.get("phone") or "").lower()

                if field_filter == "name":
                    matched = search in name
                elif field_filter == "serial":
                    matched = search == sn_str or search in ec_no
                elif field_filter == "employer":
                    matched = search in employer
                elif field_filter == "agency":
                    matched = search in agency or search in agency_lic or search in agency_phone
                elif field_filter == "year":
                    matched = search in r_year
                else:
                    matched = (
                        search in name or
                        search in sn_str or
                        search in ec_no or
                        search in employer or
                        search in agency or
                        search in agency_lic or
                        search in agency_phone or
                        search == r_year
                    )
                if matched:
                    filtered.append(r)
        else:
            filtered = list(records)

        # Sorting: support multi-year serial sorting
        if sort_by == "serial_asc":
            filtered.sort(key=lambda x: (int(get_record_year(x, 0)), int(x.get("serial_number", 0))))
        elif sort_by == "name_asc":
            filtered.sort(key=lambda x: x.get("candidate_name", "").lower())
        elif sort_by == "name_desc":
            filtered.sort(key=lambda x: x.get("candidate_name", "").lower(), reverse=True)
        elif sort_by == "date_desc":
            filtered.sort(key=lambda x: parse_ec_date(x.get("ec_date")), reverse=True)
        elif sort_by == "date_asc":
            filtered.sort(key=lambda x: parse_ec_date(x.get("ec_date")))
        else:
            # Default: serial_desc (highest year and serial first)
            filtered.sort(key=lambda x: (int(get_record_year(x, 0)), int(x.get("serial_number", 0))), reverse=True)

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
            "selected_year": year_param,
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
        year_param = params.get("year", [""])[0].strip()

        if code not in COUNTRY_META or not serial_str:
            self.send_json({"error": "Invalid country code or serial number"}, status_code=400)
            return

        try:
            target_sn = int(serial_str)
        except ValueError:
            self.send_json({"error": "Invalid serial format"}, status_code=400)
            return

        records = get_country_records(code, year_param or None)
        for r in records:
            if r.get("serial_number") == target_sn:
                r_year = get_record_year(r, "")
                if year_param and str(r_year) != str(year_param):
                    continue
                self.send_json({"card": r})
                return

        self.send_json({"error": f"Card {code}-{target_sn} not found"}, status_code=404)

    def handle_get_stats(self, params):
        year_filter = params.get("year", ["all"])[0].strip()
        available_years = discover_years()
        curr_year = str(datetime.datetime.now().year)

        total_valid = 0
        countries_stats = []
        for code, meta in COUNTRY_META.items():
            records = get_country_records(code, year_filter)
            count = len(records)
            total_valid += count
            countries_stats.append({
                "country_name": meta["name"],
                "country_code": code,
                "flag": meta.get("flag", "🌐"),
                "total_valid_records": count,
                "highest_serial": max([r["serial_number"] for r in records]) if records else 6000001
            })

        self.send_json({
            "selected_year": year_filter,
            "available_years": available_years,
            "current_year": curr_year,
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
        slug = COUNTRY_META[code]["slug"]
        check_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_year = str(datetime.datetime.now().year)

        requested_year = body.get("year")
        # Determine which years to check
        if requested_year and str(requested_year).lower() not in ("all", "auto"):
            years_to_check = [str(requested_year).strip()]
        else:
            # Auto mode: check current calendar year
            years_to_check = [current_year]
            # If in transition or if prior year has records, ensure prior year is checked too
            prior_year = str(int(current_year) - 1)
            prior_file = get_country_filepath(code, prior_year)
            if os.path.exists(prior_file) and prior_year not in years_to_check:
                years_to_check.append(prior_year)

        print(f"[{code}] Checking for new cards for years {years_to_check} at {check_time_str}...")

        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=2)
        s.mount("https://", adapter)
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        })

        all_new_cards = []
        errors_encountered = []
        latest_serials_by_year = {}

        for target_year in years_to_check:
            filepath = get_country_filepath(code, target_year)
            existing_records = get_country_records_for_year(code, target_year)
            current_highest = max([r["serial_number"] for r in existing_records]) if existing_records else 6000000
            start_probe_sn = current_highest + 1

            new_cards_this_year = []
            curr_sn = start_probe_sn
            consecutive_misses = 0
            max_miss_limit = 5

            while consecutive_misses < max_miss_limit:
                url = f"https://raims.oep.gov.bd/ec-card/verify/{code}-I-{target_year}-{curr_sn}"
                try:
                    s.cookies.clear()
                    r = s.get(url, allow_redirects=False, timeout=8)
                    if r.status_code == 200:
                        card_data = parse_card_html(r.text, url, country_name, code, curr_sn, target_year)
                        new_cards_this_year.append(card_data)
                        consecutive_misses = 0
                        print(f"[{code}-{target_year}] Found new valid card: {curr_sn} ({card_data.get('candidate_name')})")
                    elif r.status_code == 302:
                        consecutive_misses += 1
                    else:
                        errors_encountered.append(f"[{target_year}] SN {curr_sn}: HTTP {r.status_code}")
                        consecutive_misses += 1
                except Exception as e:
                    errors_encountered.append(f"[{target_year}] SN {curr_sn}: {str(e)}")
                    consecutive_misses += 1

                curr_sn += 1

            # Look-ahead probes if none found immediately and we have prior records
            if not new_cards_this_year and current_highest > 6000000:
                lookahead = [current_highest + 5, current_highest + 15, current_highest + 30]
                for p_sn in lookahead:
                    try:
                        s.cookies.clear()
                        p_url = f"https://raims.oep.gov.bd/ec-card/verify/{code}-I-{target_year}-{p_sn}"
                        r = s.get(p_url, allow_redirects=False, timeout=6)
                        if r.status_code == 200:
                            card_data = parse_card_html(r.text, p_url, country_name, code, p_sn, target_year)
                            new_cards_this_year.append(card_data)
                            print(f"[{code}-{target_year}] Found look-ahead card: {p_sn}")
                    except Exception:
                        pass

            # Save if new cards found for this year
            if new_cards_this_year:
                sn_map = {r["serial_number"]: r for r in existing_records}
                for nc in new_cards_this_year:
                    sn_map[nc["serial_number"]] = nc

                merged_records = sorted(sn_map.values(), key=lambda x: x["serial_number"])

                tmp_filepath = filepath + ".tmp"
                with open(tmp_filepath, "w", encoding="utf-8") as f:
                    json.dump(merged_records, f, indent=2, ensure_ascii=False)
                os.replace(tmp_filepath, filepath)

                # Invalidate cache
                cache_key = (code, target_year)
                if cache_key in DATASET_CACHE:
                    del DATASET_CACHE[cache_key]

                updated_highest = max(sn_map.keys())
                latest_serials_by_year[target_year] = updated_highest
                last_rec = merged_records[-1]

                update_summary_entry(code, target_year, updated_highest, len(merged_records), last_rec, check_time_str)
                all_new_cards.extend(new_cards_this_year)
            else:
                latest_serials_by_year[target_year] = current_highest
                last_rec = existing_records[-1] if existing_records else {}
                if existing_records:
                    update_summary_entry(code, target_year, current_highest, len(existing_records), last_rec, check_time_str)

        # Build response
        primary_year = years_to_check[0]
        total_valid = len(get_country_records(code, requested_year or "all"))

        if all_new_cards:
            self.send_json({
                "status": "success",
                "country_code": code,
                "country_name": country_name,
                "year": primary_year,
                "checked_years": years_to_check,
                "new_cards_count": len(all_new_cards),
                "new_cards": all_new_cards,
                "latest_serial_number": latest_serials_by_year.get(primary_year, 6000001),
                "latest_serials_by_year": latest_serials_by_year,
                "total_valid_records": total_valid,
                "check_time": check_time_str,
                "message": f"Successfully fetched and saved {len(all_new_cards)} newly issued card(s) for {country_name}!",
                "errors": errors_encountered if errors_encountered else None
            })
        else:
            self.send_json({
                "status": "success",
                "country_code": code,
                "country_name": country_name,
                "year": primary_year,
                "checked_years": years_to_check,
                "new_cards_count": 0,
                "new_cards": [],
                "latest_serial_number": latest_serials_by_year.get(primary_year, 6000001),
                "latest_serials_by_year": latest_serials_by_year,
                "total_valid_records": total_valid,
                "check_time": check_time_str,
                "message": "No new cards found.",
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
