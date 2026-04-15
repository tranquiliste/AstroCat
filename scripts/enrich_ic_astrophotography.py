#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


ROOT = Path(__file__).resolve().parents[1]
IC_META_PATH = ROOT / "data" / "ic_catalog.json"
OPENNGC_PATH = ROOT / "data" / "openngc" / "NGC.csv"
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKI_API = "https://en.wikipedia.org/w/api.php"

MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

TYPE_MAP = {
    "*": "Star",
    "**": "Double Star",
    "*Ass": "Association of Stars",
    "OCl": "Open Cluster",
    "GCl": "Globular Cluster",
    "Cl+N": "Cluster + Nebula",
    "G": "Galaxy",
    "GPair": "Galaxy Pair",
    "GTrpl": "Galaxy Triplet",
    "GGroup": "Galaxy Group",
    "PN": "Planetary Nebula",
    "HII": "HII Region",
    "DrkN": "Dark Nebula",
    "EmN": "Emission Nebula",
    "Neb": "Nebula",
    "RfN": "Reflection Nebula",
    "SNR": "Supernova Remnant",
    "Nova": "Nova",
    "NonEx": "Nonexistent Object",
    "Dup": "Duplicate Entry",
    "Other": "Other",
}

CONSTELLATION_ABBREVIATIONS = {
    "And": "Andromeda",
    "Ant": "Antlia",
    "Aps": "Apus",
    "Aql": "Aquila",
    "Aqr": "Aquarius",
    "Ara": "Ara",
    "Ari": "Aries",
    "Aur": "Auriga",
    "Boo": "Bootes",
    "CMa": "Canis Major",
    "CMi": "Canis Minor",
    "CVn": "Canes Venatici",
    "Cae": "Caelum",
    "Cam": "Camelopardalis",
    "Cap": "Capricornus",
    "Car": "Carina",
    "Cas": "Cassiopeia",
    "Cen": "Centaurus",
    "Cep": "Cepheus",
    "Cet": "Cetus",
    "Cha": "Chamaeleon",
    "Cnc": "Cancer",
    "Col": "Columba",
    "Com": "Coma Berenices",
    "CrA": "Corona Australis",
    "CrB": "Corona Borealis",
    "Crt": "Crater",
    "Crv": "Corvus",
    "Cyg": "Cygnus",
    "Del": "Delphinus",
    "Dor": "Dorado",
    "Dra": "Draco",
    "Equ": "Equuleus",
    "Eri": "Eridanus",
    "For": "Fornax",
    "Gem": "Gemini",
    "Gru": "Grus",
    "Her": "Hercules",
    "Hor": "Horologium",
    "Hya": "Hydra",
    "Hyi": "Hydrus",
    "Ind": "Indus",
    "LMi": "Leo Minor",
    "Lac": "Lacerta",
    "Leo": "Leo",
    "Lep": "Lepus",
    "Lib": "Libra",
    "Lup": "Lupus",
    "Lyn": "Lynx",
    "Lyr": "Lyra",
    "Men": "Mensa",
    "Mic": "Microscopium",
    "Mon": "Monoceros",
    "Mus": "Musca",
    "Nor": "Norma",
    "Oct": "Octans",
    "Oph": "Ophiuchus",
    "Ori": "Orion",
    "Pav": "Pavo",
    "Peg": "Pegasus",
    "Per": "Perseus",
    "Phe": "Phoenix",
    "Pic": "Pictor",
    "PsA": "Piscis Austrinus",
    "Psc": "Pisces",
    "Pup": "Puppis",
    "Pyx": "Pyxis",
    "Ret": "Reticulum",
    "Scl": "Sculptor",
    "Sco": "Scorpius",
    "Sct": "Scutum",
    "Se1": "Serpens",
    "Se2": "Serpens",
    "Sex": "Sextans",
    "Sge": "Sagitta",
    "Sgr": "Sagittarius",
    "Tau": "Taurus",
    "Tel": "Telescopium",
    "TrA": "Triangulum Australe",
    "Tri": "Triangulum",
    "Tuc": "Tucana",
    "UMa": "Ursa Major",
    "UMi": "Ursa Minor",
    "Vel": "Vela",
    "Vir": "Virgo",
    "Vol": "Volans",
    "Vul": "Vulpecula",
}

TYPE_SCORES = {
    "Emission Nebula": 130.0,
    "HII Region": 128.0,
    "Reflection Nebula": 124.0,
    "Dark Nebula": 120.0,
    "Planetary Nebula": 118.0,
    "Supernova Remnant": 114.0,
    "Cluster + Nebula": 110.0,
    "Open Cluster": 90.0,
    "Globular Cluster": 86.0,
    "Nebula": 82.0,
    "Association of Stars": 60.0,
    "Galaxy": 58.0,
    "Galaxy Pair": 50.0,
    "Galaxy Triplet": 46.0,
    "Galaxy Group": 40.0,
    "Other": -80.0,
    "Star": -120.0,
    "Double Star": -120.0,
    "Duplicate Entry": -200.0,
    "Nonexistent Object": -200.0,
}

KEYWORD_BONUSES = {
    "nebula": 18.0,
    "galaxy": 10.0,
    "cluster": 10.0,
    "heart": 26.0,
    "soul": 26.0,
    "pelican": 24.0,
    "flame": 24.0,
    "flaming star": 24.0,
    "jellyfish": 24.0,
    "cocoon": 22.0,
    "ghost": 18.0,
    "spider": 18.0,
    "fly": 18.0,
    "iris": 18.0,
    "shrimp": 22.0,
    "tadpoles": 22.0,
    "star queen": 18.0,
    "rosette": 18.0,
    "eagle": 16.0,
}

GENERIC_PAGE_TITLES = {
    "List of IC objects",
    "Index Catalogue",
    "New General Catalogue",
    "List of NGC objects",
}


@dataclass
class WikiRecord:
    item_id: Optional[str] = None
    discoverer_id: Optional[str] = None
    discovery_year: Optional[int] = None
    distance_ly: Optional[float] = None


@dataclass
class OpenNGCRecord:
    common_name: Optional[str] = None
    description: Optional[str] = None
    object_type: Optional[str] = None
    constellation: Optional[str] = None
    ra_hours: Optional[float] = None
    dec_deg: Optional[float] = None
    major_axis_arcmin: Optional[float] = None
    visual_mag: Optional[float] = None
    blue_mag: Optional[float] = None


@dataclass
class WikiInfo:
    title: str
    extract: str
    fullurl: str
    thumbnail: Optional[str] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich the top IC astrophotography targets.")
    parser.add_argument("--limit", type=int, default=300, help="Number of IC targets to enrich (default: 300)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the selected targets without modifying ic_catalog.json.",
    )
    return parser.parse_args()


def _fetch_json(url: str, retries: int = 4) -> Dict:
    for attempt in range(1, retries + 1):
        result = subprocess.run(
            [
                "curl",
                "-sL",
                "--retry",
                "4",
                "--retry-delay",
                "1",
                "-H",
                "User-Agent: AstroCat/1.0",
                url,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = result.stdout.strip()
        if payload:
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                pass
        time.sleep(1.5 * attempt)
    raise RuntimeError("Failed to fetch valid JSON response.")


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_ra_hours(ra_text: str) -> Optional[float]:
    if not ra_text:
        return None
    parts = ra_text.split(":")
    try:
        hours = float(parts[0])
        minutes = float(parts[1]) if len(parts) > 1 else 0.0
        seconds = float(parts[2]) if len(parts) > 2 else 0.0
    except ValueError:
        return None
    return hours + minutes / 60.0 + seconds / 3600.0


def _parse_dec_deg(dec_text: str) -> Optional[float]:
    if not dec_text:
        return None
    sign = -1.0 if dec_text.strip().startswith("-") else 1.0
    text = dec_text.strip().lstrip("+-")
    parts = text.split(":")
    try:
        deg = float(parts[0])
        minutes = float(parts[1]) if len(parts) > 1 else 0.0
        seconds = float(parts[2]) if len(parts) > 2 else 0.0
    except ValueError:
        return None
    return sign * (deg + minutes / 60.0 + seconds / 3600.0)


def _best_months_from_ra(ra_hours: Optional[float]) -> Optional[str]:
    if ra_hours is None:
        return None
    month_index = int((ra_hours / 2 + 9) % 12)
    if month_index == 0:
        month_index = 12
    idx = month_index - 1
    return f"{MONTHS[(idx - 1) % 12]}{MONTHS[idx]}{MONTHS[(idx + 1) % 12]}"


def _load_openngc() -> Dict[str, OpenNGCRecord]:
    records: Dict[str, OpenNGCRecord] = {}
    if not OPENNGC_PATH.exists():
        return records
    with OPENNGC_PATH.open(newline="", encoding="utf-8", errors="replace") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            name = (row.get("Name") or "").strip()
            if not name:
                continue
            match = re.match(r"^(IC)\s*0*([0-9]+[A-Z]?)$", name, re.IGNORECASE)
            if not match:
                continue
            object_id = f"IC{match.group(2).upper()}"
            common = (row.get("Common names") or "").strip() or None
            if common:
                common = re.split(r"[;,/]", common)[0].strip()
            description = (row.get("OpenNGC notes") or "").strip() or (row.get("NED notes") or "").strip() or None
            type_code = (row.get("Type") or "").strip()
            constellation = CONSTELLATION_ABBREVIATIONS.get((row.get("Const") or "").strip())
            records[object_id] = OpenNGCRecord(
                common_name=common,
                description=description,
                object_type=TYPE_MAP.get(type_code, type_code) or None,
                constellation=constellation,
                ra_hours=_parse_ra_hours((row.get("RA") or "").strip()),
                dec_deg=_parse_dec_deg((row.get("Dec") or "").strip()),
                major_axis_arcmin=_parse_float(row.get("MajAx")),
                visual_mag=_parse_float(row.get("V-Mag")),
                blue_mag=_parse_float(row.get("B-Mag")),
            )
    return records


def _score_astrophotography_target(object_id: str, meta: Dict, record: OpenNGCRecord) -> float:
    object_type = record.object_type or (meta.get("type") or "")
    score = TYPE_SCORES.get(object_type, 0.0)
    if record.common_name:
        score += 44.0
    mag = record.visual_mag if record.visual_mag is not None else record.blue_mag
    if mag is not None:
        score += max(0.0, 20.0 - 1.3 * mag)
    if record.major_axis_arcmin is not None:
        score += min(30.0, record.major_axis_arcmin * 1.6)
        if record.major_axis_arcmin >= 30.0:
            score += 10.0
        elif record.major_axis_arcmin >= 10.0:
            score += 6.0
        elif record.major_axis_arcmin <= 1.0 and object_type == "Galaxy":
            score -= 8.0
    haystack = " ".join(
        part for part in [record.common_name or "", record.description or "", object_type or "", object_id] if part
    ).lower()
    for keyword, bonus in KEYWORD_BONUSES.items():
        if keyword in haystack:
            score += bonus
    if meta.get("description"):
        score += 6.0
    if meta.get("wiki_thumbnail"):
        score += 4.0
    if meta.get("name"):
        score += 3.0
    return score


def _select_priority_object_ids(entries: Dict[str, Dict], openngc: Dict[str, OpenNGCRecord], limit: int) -> list[str]:
    scored: list[tuple[float, str, str]] = []
    for object_id, meta in entries.items():
        if not isinstance(meta, dict):
            continue
        record = openngc.get(object_id)
        if not record:
            continue
        object_type = record.object_type or (meta.get("type") or "")
        if object_type in {"Duplicate Entry", "Nonexistent Object", "Star", "Double Star", "Other"}:
            continue
        scored.append((_score_astrophotography_target(object_id, meta, record), object_id, object_type))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [object_id for _score, object_id, _type in scored[:limit]]


def _sparql_query(query: str) -> Dict:
    params = urllib.parse.urlencode({"format": "json", "query": query})
    return _fetch_json(f"{WIKIDATA_ENDPOINT}?{params}")


def _iter_wikidata_rows(object_ids: Iterable[str], batch_size: int = 50) -> Iterable[Dict]:
    ids: list[int] = []
    for object_id in object_ids:
        match = re.match(r"IC\s*0*(\d+)", object_id, re.IGNORECASE)
        if match:
            ids.append(int(match.group(1)))
    ids.sort()
    total_batches = ((len(ids) - 1) // batch_size) + 1 if ids else 0
    for start in range(0, len(ids), batch_size):
        batch = ids[start : start + batch_size]
        values = " ".join(f'"IC {num}"' for num in batch)
        print(f"Fetching Wikidata batch {start // batch_size + 1} / {total_batches}...")
        query = f'''
SELECT ?item ?ic ?discoverer ?discovery ?distanceAmount ?distanceUnit WHERE {{
  VALUES ?ic {{ {values} }}
  ?item wdt:P528 ?ic .
  OPTIONAL {{ ?item wdt:P61 ?discoverer . }}
  OPTIONAL {{ ?item wdt:P575 ?discovery . }}
  OPTIONAL {{
    ?item p:P2583/psv:P2583 ?distanceNode .
    ?distanceNode wikibase:quantityAmount ?distanceAmount ;
                  wikibase:quantityUnit ?distanceUnit .
  }}
}}
'''
        for row in _sparql_query(query).get("results", {}).get("bindings", []):
            yield row
        time.sleep(0.2)


def _parse_ic_code(value: str) -> Optional[str]:
    match = re.search(r"IC\s*0*(\d+)", value, re.IGNORECASE)
    return f"IC{int(match.group(1))}" if match else None


def _parse_discovery_year(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.match(r"^(\d{4})", value)
    return int(match.group(1)) if match else None


def _convert_distance_to_ly(amount: Optional[str], unit: Optional[str]) -> Optional[float]:
    if not amount or not unit:
        return None
    try:
        value = float(amount)
    except ValueError:
        return None
    unit_id = unit.rsplit("/", 1)[-1]
    if unit_id == "Q531":
        return value
    if unit_id == "Q12129":
        return value * 3.26156
    if unit_id == "Q11929860":
        return value * 3261.56
    if unit_id == "Q3773454":
        return value * 3_261_560.0
    return None


def _choose_distance(existing: Optional[float], candidate: Optional[float], unit: Optional[str]) -> Optional[float]:
    if candidate is None:
        return existing
    if existing is None:
        return candidate
    if unit and unit.rsplit("/", 1)[-1] == "Q531":
        return candidate
    return existing


def _build_wiki_index(object_ids: Iterable[str]) -> Dict[str, WikiRecord]:
    wiki: Dict[str, WikiRecord] = {}
    for row in _iter_wikidata_rows(object_ids):
        ic_value = row.get("ic", {}).get("value")
        object_id = _parse_ic_code(ic_value or "")
        if not object_id:
            continue
        record = wiki.setdefault(object_id, WikiRecord())
        item_uri = row.get("item", {}).get("value")
        if item_uri:
            record.item_id = record.item_id or item_uri.rsplit("/", 1)[-1]
        discoverer_uri = row.get("discoverer", {}).get("value")
        if discoverer_uri:
            record.discoverer_id = record.discoverer_id or discoverer_uri.rsplit("/", 1)[-1]
        discovery_year = _parse_discovery_year(row.get("discovery", {}).get("value"))
        if discovery_year:
            record.discovery_year = record.discovery_year or discovery_year
        distance_amount = row.get("distanceAmount", {}).get("value")
        distance_unit = row.get("distanceUnit", {}).get("value")
        record.distance_ly = _choose_distance(
            record.distance_ly,
            _convert_distance_to_ly(distance_amount, distance_unit),
            distance_unit,
        )
    return wiki


def _fetch_label_batch(qids: Iterable[str]) -> Dict[str, str]:
    ids = "|".join(sorted(set(qids)))
    if not ids:
        return {}
    params = urllib.parse.urlencode(
        {
            "action": "wbgetentities",
            "ids": ids,
            "props": "labels",
            "languages": "en",
            "format": "json",
        }
    )
    data = _fetch_json(f"{WIKIDATA_API}?{params}")
    labels: Dict[str, str] = {}
    for qid, entity in data.get("entities", {}).items():
        label = entity.get("labels", {}).get("en", {}).get("value")
        if label:
            labels[qid] = label
    return labels


def _fetch_labels(qids: Iterable[str]) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    batch: list[str] = []
    for qid in qids:
        if qid and qid not in labels:
            batch.append(qid)
        if len(batch) >= 50:
            labels.update(_fetch_label_batch(batch))
            batch.clear()
    if batch:
        labels.update(_fetch_label_batch(batch))
    return labels


def _title_from_object_id(object_id: str) -> Optional[str]:
    match = re.match(r"^IC\s*0*(\d+)([A-Z]?)$", object_id.strip(), re.IGNORECASE)
    if not match:
        return None
    return f"IC {int(match.group(1))}{match.group(2).upper() if match.group(2) else ''}"


def _fetch_wiki_batch(titles: list[str]) -> Dict[str, WikiInfo]:
    params = {
        "action": "query",
        "format": "json",
        "prop": "pageimages|extracts|info",
        "redirects": "1",
        "titles": "|".join(titles),
        "exintro": "1",
        "explaintext": "1",
        "exsentences": "2",
        "piprop": "thumbnail",
        "pithumbsize": "640",
        "inprop": "url",
        "formatversion": "2",
    }
    data = _fetch_json(f"{WIKI_API}?{urllib.parse.urlencode(params)}")
    query = data.get("query", {})
    normalized = {row.get("from"): row.get("to") for row in query.get("normalized", [])}
    redirects = {row.get("from"): row.get("to") for row in query.get("redirects", [])}
    pages_by_title = {
        page.get("title"): page
        for page in query.get("pages", [])
        if not page.get("missing")
    }
    info_by_title: Dict[str, WikiInfo] = {}
    for title in titles:
        resolved = redirects.get(normalized.get(title, title), normalized.get(title, title))
        page = pages_by_title.get(resolved)
        if not page:
            continue
        extract = (page.get("extract") or "").strip()
        if not extract:
            continue
        info_by_title[title] = WikiInfo(
            title=page.get("title", resolved),
            extract=extract,
            fullurl=page.get("fullurl", ""),
            thumbnail=(page.get("thumbnail") or {}).get("source"),
        )
    return info_by_title


def _fetch_wiki_info(titles: Iterable[str], batch_size: int = 50) -> Dict[str, WikiInfo]:
    results: Dict[str, WikiInfo] = {}
    batch: list[str] = []
    for title in titles:
        if title in results:
            continue
        batch.append(title)
        if len(batch) >= batch_size:
            results.update(_fetch_wiki_batch(batch))
            batch.clear()
            time.sleep(0.2)
    if batch:
        results.update(_fetch_wiki_batch(batch))
    return results


def _looks_astronomy_page(info: WikiInfo, object_type: Optional[str]) -> bool:
    text = f"{info.title} {info.extract}".lower()
    if "may refer to" in text or "disambiguation" in text:
        return False
    if info.title in GENERIC_PAGE_TITLES:
        return False
    bad_keywords = (
        "railroad", "railway", "locomotive", "diesel", "steam", "train", "station",
        "aircraft", "ship", "submarine", "destroyer", "highway", "road", "bridge",
        "building", "company", "corporation", "album", "song", "band", "film",
        "television", "episode", "novel", "comic", "manga", "school", "university",
    )
    if any(keyword in text for keyword in bad_keywords):
        return False
    good_keywords = (
        "galaxy", "nebula", "cluster", "planetary nebula", "supernova", "emission nebula",
        "reflection nebula", "dark nebula", "constellation", "astronomical", "deep-sky",
        "interstellar", "h ii", "hii", "open cluster", "globular cluster",
    )
    if any(keyword in text for keyword in good_keywords):
        return True
    if object_type:
        for token in re.split(r"\W+", object_type.lower()):
            if token and token in text:
                return True
    return False


def _score_wiki_candidate(info: WikiInfo, object_id: str, common_name: Optional[str], object_type: Optional[str]) -> float:
    if not _looks_astronomy_page(info, object_type):
        return -1e9
    text = f"{info.title} {info.extract}".lower()
    score = 0.0
    if object_id.lower().replace("ic", "ic ") in text or object_id.lower() in text:
        score += 25.0
    title_object = _title_from_object_id(object_id)
    if title_object and info.title.lower() == title_object.lower():
        score += 30.0
    if common_name:
        folded_name = common_name.lower()
        if folded_name == info.title.lower():
            score += 35.0
        elif folded_name in info.title.lower():
            score += 25.0
        elif folded_name in text:
            score += 18.0
    if "list of ic objects" in text or "index catalogue" in text:
        score -= 80.0
    if object_type and object_type.lower() in text:
        score += 10.0
    if info.thumbnail:
        score += 4.0
    return score


def _choose_best_wiki_info(
    object_id: str,
    meta: Dict,
    record: Optional[OpenNGCRecord],
    wiki_by_title: Dict[str, WikiInfo],
) -> Optional[WikiInfo]:
    candidates: list[tuple[float, WikiInfo]] = []
    title = _title_from_object_id(object_id)
    if title and title in wiki_by_title:
        info = wiki_by_title[title]
        candidates.append((_score_wiki_candidate(info, object_id, record.common_name if record else None, meta.get("type")), info))
    if record and record.common_name and record.common_name in wiki_by_title:
        info = wiki_by_title[record.common_name]
        candidates.append((_score_wiki_candidate(info, object_id, record.common_name, meta.get("type")), info))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_info = candidates[0]
    return best_info if best_score > 0 else None


def main() -> None:
    args = parse_args()
    if not IC_META_PATH.exists():
        raise SystemExit(f"Missing metadata: {IC_META_PATH}")
    data = json.loads(IC_META_PATH.read_text(encoding="utf-8"))
    entries = data.get("IC", {})
    if not isinstance(entries, dict):
        raise SystemExit("IC metadata is not a dictionary.")

    openngc = _load_openngc()
    selected_ids = _select_priority_object_ids(entries, openngc, args.limit)
    print(f"Selected {len(selected_ids)} IC targets for astrophotography enrichment.")
    for object_id in selected_ids[:25]:
        record = openngc.get(object_id)
        print(f"  - {object_id}: {(record.common_name or '')} [{record.object_type if record else ''}]")
    if args.dry_run:
        return

    wiki = _build_wiki_index(selected_ids)
    discoverer_ids = sorted({record.discoverer_id for record in wiki.values() if record.discoverer_id})
    discoverer_labels = _fetch_labels(discoverer_ids)

    title_queries = set()
    for object_id in selected_ids:
        title = _title_from_object_id(object_id)
        if title:
            title_queries.add(title)
        record = openngc.get(object_id)
        if record and record.common_name:
            title_queries.add(record.common_name)

    print(f"Fetching Wikipedia summaries for {len(title_queries)} candidate titles...")
    wiki_info = _fetch_wiki_info(sorted(title_queries))

    updated_fields = 0
    updated_wiki = 0
    for object_id in selected_ids:
        meta = entries.get(object_id)
        if not isinstance(meta, dict):
            continue
        record = openngc.get(object_id)
        wiki_record = wiki.get(object_id)

        if record and record.object_type and (not meta.get("type") or meta.get("type") == "Other"):
            meta["type"] = record.object_type
            updated_fields += 1
        if record and record.common_name and not meta.get("name"):
            meta["name"] = record.common_name
            updated_fields += 1
        if record and record.constellation and not meta.get("constellation"):
            meta["constellation"] = record.constellation
            updated_fields += 1
        if record and record.ra_hours is not None and not meta.get("ra_hours"):
            meta["ra_hours"] = record.ra_hours
            updated_fields += 1
        if record and record.dec_deg is not None and not meta.get("dec_deg"):
            meta["dec_deg"] = record.dec_deg
            updated_fields += 1
        if not meta.get("best_months"):
            best_months = _best_months_from_ra(record.ra_hours if record else meta.get("ra_hours"))
            if best_months:
                meta["best_months"] = best_months
                updated_fields += 1
        if meta.get("discoverer") is None and wiki_record and wiki_record.discoverer_id:
            label = discoverer_labels.get(wiki_record.discoverer_id)
            if label:
                meta["discoverer"] = label
                updated_fields += 1
        if meta.get("discovery_year") is None and wiki_record and wiki_record.discovery_year:
            meta["discovery_year"] = wiki_record.discovery_year
            updated_fields += 1
        if meta.get("distance_ly") is None and wiki_record and wiki_record.distance_ly is not None:
            meta["distance_ly"] = round(wiki_record.distance_ly, 1)
            updated_fields += 1

        chosen_info = _choose_best_wiki_info(object_id, meta, record, wiki_info)
        if chosen_info:
            if meta.get("description") != chosen_info.extract:
                meta["description"] = chosen_info.extract
                updated_wiki += 1
            if chosen_info.fullurl and meta.get("external_link") != chosen_info.fullurl:
                meta["external_link"] = chosen_info.fullurl
                updated_wiki += 1
            if chosen_info.thumbnail and meta.get("wiki_thumbnail") != chosen_info.thumbnail:
                meta["wiki_thumbnail"] = chosen_info.thumbnail
                updated_wiki += 1
        elif record and record.description and not meta.get("description"):
            meta["description"] = record.description
            updated_wiki += 1

    IC_META_PATH.write_text(json.dumps({"IC": entries}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated structural fields: {updated_fields}")
    print(f"Updated description/wiki fields: {updated_wiki}")


if __name__ == "__main__":
    main()
