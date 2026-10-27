"""Offline basemap for the standalone HTML: Natural Earth (public domain) clipped to the AfPak region -> basemap.json
Inputs (zips in --src): ne_50m_admin_0_countries, ne_10m_admin_1_states_provinces, ne_10m_populated_places_simple, ne_50m_rivers_lake_centerlines, ne_50m_lakes."""
import argparse, io, json, zipfile, shapefile
BBOX = (52.0, 20.0, 82.0, 44.0)  # lon0, lat0, lon1, lat1

def rd(zpath):
    z = zipfile.ZipFile(zpath); shp = [n for n in z.namelist() if n.endswith('.shp')][0]
    return shapefile.Reader(shp=io.BytesIO(z.read(shp)), dbf=io.BytesIO(z.read(shp[:-4] + '.dbf')), shx=io.BytesIO(z.read(shp[:-4] + '.shx')))

def inbox(b):  # feature bbox intersects region bbox
    return not (b[2] < BBOX[0] or b[0] > BBOX[2] or b[3] < BBOX[1] or b[1] > BBOX[3])

def feats(zpath, keep, props, rnd=3):
    out = []
    for sr in rd(zpath).iterShapeRecords():
        if sr.shape.shapeType == 0: continue
        g = sr.shape.__geo_interface__; r = sr.record.as_dict()
        if g['type'] == 'Point':
            x, y = g['coordinates']
            if not (BBOX[0] <= x <= BBOX[2] and BBOX[1] <= y <= BBOX[3]): continue
        elif not inbox(sr.shape.bbox): continue
        if not keep(r): continue
        def rn(c):
            return [rn(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], rnd), round(c[1], rnd)]
        g['coordinates'] = rn(g['coordinates'])
        out.append({'type': 'Feature', 'geometry': g, 'properties': {k: r.get(s) for k, s in props.items()}})
    return {'type': 'FeatureCollection', 'features': out}

ap = argparse.ArgumentParser(); ap.add_argument('--src', default='/tmp/ne'); ap.add_argument('--out', default='basemap.json'); a = ap.parse_args()
bm = {
  'countries': feats(f'{a.src}/adm0.zip', lambda r: True, {'name': 'NAME', 'iso': 'ISO_A2'}, 2),
  'provinces': feats(f'{a.src}/adm1.zip', lambda r: r.get('adm0_a3') in ('AFG', 'PAK', 'IRN', 'TJK', 'UZB', 'TKM', 'IND', 'CHN', 'KGZ'), {'name': 'name', 'country': 'adm0_a3'}, 2),
  'places': feats(f'{a.src}/places.zip', lambda r: (r.get('scalerank') or 10) <= 7, {'name': 'name', 'rank': 'scalerank', 'capital': 'featurecla'}, 3),
  'rivers': feats(f'{a.src}/rivers.zip', lambda r: True, {'name': 'name'}, 2),
  'lakes': feats(f'{a.src}/lakes.zip', lambda r: True, {'name': 'name'}, 2),
}
bm['attribution'] = 'Basemap: Natural Earth (public domain), clipped to the AfPak region for offline use'
json.dump(bm, open(a.out, 'w'), separators=(',', ':'))
print({k: len(v['features']) for k, v in bm.items() if isinstance(v, dict)}, 'bytes', len(json.dumps(bm, separators=(',', ':'))))
