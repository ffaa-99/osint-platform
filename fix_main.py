with open('app/main.py', 'r', encoding='utf-8') as f:
    c = f.read()

if 'reverse_geocode(coords' in c:
    print('ALREADY FIXED')
else:
    target = 'result["map_url"] = f"https://maps.google.com/?q={coords[\'lat\']},{coords[\'lon\']}"'
    replacement = target + '\n            result["location"] = reverse_geocode(coords["lat"], coords["lon"])'
    c = c.replace(target, replacement)
    with open('app/main.py', 'w', encoding='utf-8') as f:
        f.write(c)
    print('FIXED OK')