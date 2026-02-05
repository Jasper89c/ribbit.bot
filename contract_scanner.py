# contract_scanner.py

import csv
from collections import Counter
from esi_auth import esi_get, get_access_token, ESI_BASE

CORP_ID = 98820373

type_cache = {}
group_cache = {}
category_cache = {}
location_cache = {}


def get_type_info(type_id):
    if type_id in type_cache:
        return type_cache[type_id]

    url = f"{ESI_BASE}/universe/types/{type_id}/"
    data = esi_get(url)
    if not data:
        info = {"name": f"Type {type_id}", "group_id": None, "category_id": None}
        type_cache[type_id] = info
        return info

    group_id = data.get("group_id")
    category_id = None

    if group_id:
        g_url = f"{ESI_BASE}/universe/groups/{group_id}/"
        g_data = esi_get(g_url)
        if g_data:
            category_id = g_data.get("category_id")
            group_cache[group_id] = g_data.get("name")

    info = {
        "name": data.get("name", f"Type {type_id}"),
        "group_id": group_id,
        "category_id": category_id,
    }
    type_cache[type_id] = info
    return info


def is_ship(type_id):
    info = get_type_info(type_id)
    cat_id = info["category_id"]
    if cat_id is None:
        return False

    if cat_id in category_cache:
        return category_cache[cat_id] == "Ship"

    url = f"{ESI_BASE}/universe/categories/{cat_id}/"
    data = esi_get(url)
    name = data.get("name", "Unknown") if data else "Unknown"
    category_cache[cat_id] = name
    return name == "Ship"


def get_location_name(location_id):
    if not location_id:
        return "Unknown"

    if location_id in location_cache:
        return location_cache[location_id]

    if location_id < 1_000_000_000:
        url = f"{ESI_BASE}/universe/stations/{location_id}/"
        data = esi_get(url)
        if data:
            name = data.get("name", f"Station {location_id}")
            location_cache[location_id] = name
            return name

    url = f"{ESI_BASE}/universe/structures/{location_id}/"
    data = esi_get(url)
    if data:
        name = data.get("name", f"Structure {location_id}")
        location_cache[location_id] = name
        return name

    location_cache[location_id] = f"Location {location_id}"
    return location_cache[location_id]


def get_corp_contracts(corp_id):
    contracts = []
    page = 1
    while True:
        url = f"{ESI_BASE}/corporations/{corp_id}/contracts/"
        data = esi_get(url, params={"page": page})
        if not data:
            break
        contracts.extend(data)
        page += 1
    return contracts


def get_contract_items(corp_id, contract_id):
    url = f"{ESI_BASE}/corporations/{corp_id}/contracts/{contract_id}/items/"
    return esi_get(url)


def scan_contracts():
    """Runs the full scan and returns (ship_counts, total_contracts)."""

    get_access_token()

    contracts = get_corp_contracts(CORP_ID)
    item_exchange = [
        c for c in contracts
        if c.get("type") == "item_exchange" and c.get("status") == "outstanding"
    ]

    ship_counts = Counter()
    aldranette_contract_count = 0

    for c in item_exchange:
        cid = c["contract_id"]
        loc_id = c.get("start_location_id")
        loc_name = get_location_name(loc_id)

        if "aldranette" not in loc_name.lower():
            continue

        aldranette_contract_count += 1

        items = get_contract_items(CORP_ID, cid)
        if not items:
            continue

        for it in items:
            type_id = it.get("type_id")
            qty = it.get("quantity", 0)
            if type_id and qty > 0 and is_ship(type_id):
                name = get_type_info(type_id)["name"]
                ship_counts[name] += qty

    return ship_counts, aldranette_contract_count
