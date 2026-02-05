# contract_scanner.py

import asyncio
from collections import Counter
from typing import Dict, Tuple

from esi_auth import esi_get, ESI_BASE

CORP_ID = 98820373

type_cache: Dict[int, dict] = {}
group_cache: Dict[int, str] = {}
category_cache: Dict[int, str] = {}
location_cache: Dict[int, str] = {}


async def get_type_info(type_id: int) -> dict:
    if type_id in type_cache:
        return type_cache[type_id]

    data = await esi_get(f"/universe/types/{type_id}/")
    if not data:
        info = {"name": f"Type {type_id}", "group_id": None, "category_id": None}
        type_cache[type_id] = info
        return info

    group_id = data.get("group_id")
    category_id = None

    if group_id:
        if group_id in group_cache:
            # category might already be cached via another type
            pass
        g_data = await esi_get(f"/universe/groups/{group_id}/")
        if g_data:
            category_id = g_data.get("category_id")
            group_cache[group_id] = g_data.get("name", f"Group {group_id}")

    info = {
        "name": data.get("name", f"Type {type_id}"),
        "group_id": group_id,
        "category_id": category_id,
    }
    type_cache[type_id] = info
    return info


async def is_ship(type_id: int) -> bool:
    info = await get_type_info(type_id)
    cat_id = info["category_id"]
    if cat_id is None:
        return False

    if cat_id in category_cache:
        return category_cache[cat_id] == "Ship"

    data = await esi_get(f"/universe/categories/{cat_id}/")
    name = data.get("name", "Unknown") if data else "Unknown"
    category_cache[cat_id] = name
    return name == "Ship"


async def get_location_name(location_id: int | None) -> str:
    if not location_id:
        return "Unknown"

    if location_id in location_cache:
        return location_cache[location_id]

    # Stations
    if location_id < 1_000_000_000:
        data = await esi_get(f"/universe/stations/{location_id}/")
        if data:
            name = data.get("name", f"Station {location_id}")
            location_cache[location_id] = name
            return name

    # Structures
    data = await esi_get(f"/universe/structures/{location_id}/")
    if data:
        name = data.get("name", f"Structure {location_id}")
        location_cache[location_id] = name
        return name

    location_cache[location_id] = f"Location {location_id}"
    return location_cache[location_id]


async def get_corp_contracts(corp_id: int):
    contracts = []
    page = 1
    while True:
        data = await esi_get(f"/corporations/{corp_id}/contracts/", params={"page": page})
        if not data:
            break
        contracts.extend(data)
        page += 1
    return contracts


async def get_contract_items(corp_id: int, contract_id: int):
    return await esi_get(f"/corporations/{corp_id}/contracts/{contract_id}/items/")


async def scan_contracts() -> Tuple[Counter, int]:
    """
    Runs the full scan and returns (ship_counts, total_aldranette_contracts).
    Fully async and Railway‑friendly.
    """
    contracts = await get_corp_contracts(CORP_ID)
    item_exchange = [
        c for c in contracts
        if c.get("type") == "item_exchange" and c.get("status") == "outstanding"
    ]

    ship_counts: Counter = Counter()
    aldranette_contract_count = 0

    # Pre‑fetch locations in parallel
    loc_tasks = {
        c["contract_id"]: asyncio.create_task(get_location_name(c.get("start_location_id")))
        for c in item_exchange
    }
    await asyncio.gather(*loc_tasks.values())

    # Filter to Aldranette contracts
    aldranette_contracts = []
    for c in item_exchange:
        cid = c["contract_id"]
        loc_name = loc_tasks[cid].result()
        if "aldranette" in loc_name.lower():
            aldranette_contracts.append(c)
            aldranette_contract_count += 1

    # Fetch items for all Aldranette contracts in parallel
    item_tasks = {
        c["contract_id"]: asyncio.create_task(get_contract_items(CORP_ID, c["contract_id"]))
        for c in aldranette_contracts
    }
    await asyncio.gather(*item_tasks.values())

    # Collect all type_ids to pre‑warm type cache
    type_ids = set()
    for cid, task in item_tasks.items():
        items = task.result() or []
        for it in items:
            tid = it.get("type_id")
            if tid:
                type_ids.add(tid)

    # Pre‑warm type info and ship detection in parallel
    await asyncio.gather(*(get_type_info(tid) for tid in type_ids))

    # Now count ships
    for cid, task in item_tasks.items():
        items = task.result() or []
        for it in items:
            tid = it.get("type_id")
            qty = it.get("quantity", 0)
            if not tid or qty <= 0:
                continue
            if await is_ship(tid):
                name = (await get_type_info(tid))["name"]
                ship_counts[name] += qty

    return ship_counts, aldranette_contract_count
