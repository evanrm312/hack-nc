"""Reviewed coordinates from UNC's official map (maps.unc.edu → Concept3D 111).

These are map reference markers, not verified entrance coordinates. This
read-only enrichment preserves every seed row and ID. Nullable database
metadata may supersede these references when staff verify an exact spot.
"""
CHECKED = '2026-10-10'
REFERENCES = {
    'Student Union main lobby': (35.910397, -79.047508, 1049190, 'Student Union building reference'),
    'Davis Library front entrance': (35.91103, -79.04789, 15974, 'Davis Library building reference'),
    'Rams Head Plaza': (35.906319, -79.046097, 632618, 'Rams Head Plaza map marker'),
}

def reference_for(label):
    row = REFERENCES.get(label)
    if not row:
        return {}
    lat, lon, marker, description = row
    return {'latitude':lat,'longitude':lon,'coordinate_description':description,
            'coordinate_source':f'https://map.concept3d.com/?id=111#!m/{marker}',
            'coordinates_checked_at':CHECKED}
