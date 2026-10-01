import mag.fuel_feed

def _ok_rate(meta):
    # real profile shape: {lane_id: {calls, ok, fail, ms, errors}} — no ok_rate key;
    # ok_rate is computed as ok / calls.
    calls = meta.get('calls', 0)
    return meta.get('ok', 0) / calls if calls else 0.0

def top_lanes(n=3):
    # profile()['lanes'] is a DICT keyed by lane id: {lane_id: {calls, ok, fail, ...}}
    profile_data = mag.fuel_feed.profile()
    items = list(profile_data['lanes'].items())
    sorted_lanes = sorted(items, key=lambda kv: _ok_rate(kv[1]), reverse=True)
    return [{'lane': lane_id, 'ok_rate': round(_ok_rate(meta), 3), 'calls': meta['calls']}
            for lane_id, meta in sorted_lanes[:n]]

def main():
    import json
    print(json.dumps(top_lanes(3), indent=2))
