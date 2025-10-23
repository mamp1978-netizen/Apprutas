import os, typing as t
from urllib.parse import quote_plus
import streamlit as st
try:
    import googlemaps
except Exception:
    googlemaps = None  # type: ignore

API_KEY = (st.secrets.get("GOOGLE_PLACES_API_KEY")
           or os.getenv("GOOGLE_PLACES_API_KEY")
           or st.secrets.get("GOOGLE_API_KEY")
           or os.getenv("GOOGLE_API_KEY"))

gmaps = None
if googlemaps and API_KEY:
    try: gmaps = googlemaps.Client(key=API_KEY)
    except Exception: gmaps = None

def _addr_from_any(x)->t.Optional[str]:
    if x is None: return None
    if isinstance(x,str):
        s=x.strip(); return s or None
    if isinstance(x,dict):
        a=x.get("address") or x.get("formatted_address")
        if isinstance(a,str) and a.strip(): return a.strip()
        lat=x.get("lat"); lng=x.get("lng")
        if isinstance(lat,(int,float)) and isinstance(lng,(int,float)): return f"{lat},{lng}"
        loc=(x.get("latlng") or x.get("location") or x.get("geometry",{}).get("location"))
        if isinstance(loc,dict):
            lat=loc.get("lat"); lng=loc.get("lng")
            if isinstance(lat,(int,float)) and isinstance(lng,(int,float)): return f"{lat},{lng}"
    return None

def suggest_addresses(term:str,min_len:int=3,max_results:int=8)->list[dict]:
    if not term or len(term.strip())<min_len or gmaps is None: return []
    try:
        resp=gmaps.places_autocomplete(input_text=term,types="geocode") or []
        return [{"description":r.get("description",""),
                 "place_id":r.get("place_id",""),
                 "types":r.get("types",[])} for r in resp[:max_results]]
    except Exception: return []

def resolve_selection(term:str,place_id:str|None=None)->dict:
    base={"query":term,"place_id":place_id,"address":term,"lat":None,"lng":None}
    if gmaps is None or not place_id: return base
    try:
        d=gmaps.place(place_id=place_id) or {}
        r=d.get("result",{}) if isinstance(d,dict) else {}
        addr=r.get("formatted_address") or r.get("name") or term
        loc=r.get("geometry",{}).get("location",{}) if isinstance(r,dict) else {}
        lat=loc.get("lat") if isinstance(loc,dict) else None
        lng=loc.get("lng") if isinstance(loc,dict) else None
        base.update({"address":addr,"lat":lat,"lng":lng}); return base
    except Exception: return base

def build_gmaps_url(origin,destination,waypoints=None,mode="driving",avoid=None,optimize=True):
    def _addr(x):
        a=_addr_from_any(x); return a if a else None
    o=_addr(origin); d=_addr(destination)
    if not o or not d: return None
    parts=["https://www.google.com/maps/dir/?api=1",
           f"origin={quote_plus(o)}",
           f"destination={quote_plus(d)}",
           f"travelmode={quote_plus((mode or 'driving').lower())}"]
    if avoid:
        vals=[a.strip().lower() for a in (avoid.split(",") if isinstance(avoid,str) else avoid) if str(a).strip()]
        allowed={"tolls","highways","ferries","indoor"}
        vals=[a for a in vals if a in allowed]
        if vals: parts.append(f"avoid={quote_plus(','.join(vals))}")
    if waypoints:
        if not isinstance(waypoints,(list,tuple)): waypoints=[waypoints]
        wp=[quote_plus(s) for s in (_addr(w) for w in waypoints) if s]
        if wp: parts.append(f"waypoints={('optimize:true|' if optimize else '')+'|'.join(wp)}")
    return "&".join(parts)

def build_waze_url(origin=None,destination=None):
    o=_addr_from_any(origin); d=_addr_from_any(destination)
    if not d: return None
    return (f"https://waze.com/ul?from={quote_plus(o)}&to={quote_plus(d)}&navigate=yes"
            if o else f"https://waze.com/ul?to={quote_plus(d)}&navigate=yes")

def build_apple_maps_url(origin=None,destination=None):
    o=_addr_from_any(origin); d=_addr_from_any(destination)
    if not d: return None
    parts=["http://maps.apple.com/?dirflg=d"]
    if o: parts.append(f"saddr={quote_plus(o)}")
    parts.append(f"daddr={quote_plus(d)}")
    return "&".join(parts)
