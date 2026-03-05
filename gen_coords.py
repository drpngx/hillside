
import json
import urllib.request
import re
import os

URL = "https://raw.githubusercontent.com/vial-kb/vial-qmk/1d9c72972d372d93e10fb69d56023719e03be378/keyboards/hillside/52/0_1/keyboard.json"
KEYMAP_PATH = "/home/png/hillside/zmk-config/config/boards/shields/hshs52/hshs52.keymap"

def fetch_layout():
    print(f"Fetching layout from {URL}...")
    with urllib.request.urlopen(URL) as response:
        data = json.loads(response.read().decode())
        return data["layouts"]["LAYOUT"]["layout"]

def process():
    layout = fetch_layout()
    matrix_map = {tuple(k["matrix"]): k for k in layout}

    # Order of keys in hshs52.keymap
    row0 = [(0,0), (0,1), (0,2), (0,3), (0,4), (0,5), (5,5), (5,4), (5,3), (5,2), (5,1), (5,0)]
    row1 = [(1,0), (1,1), (1,2), (1,3), (1,4), (1,5), (6,5), (6,4), (6,3), (6,2), (6,1), (6,0)]
    row2 = [(2,0), (2,1), (2,2), (2,3), (2,4), (2,5), (4,5), (9,5), (7,5), (7,4), (7,3), (7,2), (7,1), (7,0)]
    row3 = [(3,0), (3,1), (3,2), (4,1), (4,2), (4,3), (4,4), (9,4), (9,3), (9,2), (9,1), (8,2), (8,1), (8,0)]

    all_keys_indices = row0 + row1 + row2 + row3

    # Normalize Y for the outer thumb keys (Mute-Esc-Ctrl line)
    # Left: (3,0), (3,1), (3,2)
    l_outer_y = (matrix_map[(3,0)]["y"] + matrix_map[(3,1)]["y"] + matrix_map[(3,2)]["y"]) / 3
    matrix_map[(3,0)]["y"] = matrix_map[(3,1)]["y"] = matrix_map[(3,2)]["y"] = l_outer_y

    # Right: (8,2), (8,1), (8,0)
    r_outer_y = (matrix_map[(8,2)]["y"] + matrix_map[(8,1)]["y"] + matrix_map[(8,0)]["y"]) / 3
    matrix_map[(8,2)]["y"] = matrix_map[(8,1)]["y"] = matrix_map[(8,0)]["y"] = r_outer_y

    X_SCALE = 18000
    Y_SCALE = 17000

    min_x = min(k["x"] for k in layout)
    min_y = min(k["y"] for k in layout)

    lines = []
    lines.append("                keys")
    
    for i, idx in enumerate(all_keys_indices):
        k = matrix_map[idx]
        x, y = k["x"], k["y"]
        xu = int((x - min_x) * X_SCALE)
        yu = int((y - min_y) * Y_SCALE)
        rot = int(k.get("r", 0) * 1000)
        
        prefix = "                        "
        if i == 0:
            prefix += "/* Row 0 */\n                        = "
        elif i == 12:
            prefix += "/* Row 1 */\n                        , "
        elif i == 24:
            prefix += "/* Row 2 */\n                        , "
        elif i == 38:
            prefix += "/* Row 3 / Thumb Row */\n                        , "
        else:
            prefix += ", "

        # Add sub-comments for clarify if needed
        comment = ""
        if i == 41: comment = " // Thumb Arc Left"
        elif i == 45: comment = " // Thumb Arc Right"

        lines.append(f"{prefix}<&key_physical_attrs 100 100 {xu:7} {yu:7} {rot:7} 0 0>{comment}")

    keys_section = "\n".join(lines) + "\n                        ;"
    
    with open(KEYMAP_PATH, 'r') as f:
        content = f.read()

    # Regex to find the 'keys' section in physical_layout0 and replace it
    # We look for 'keys' followed by anything up to ';'
    pattern = r'(keys\s+/\* Row 0 \*/\s+=.*?;)'
    new_content = re.sub(pattern, keys_section, content, flags=re.DOTALL)

    if new_content == content:
        # Fallback if first pattern fails (might be different whitespace)
        pattern = r'(keys\s+.*?);'
        new_content = re.sub(pattern, keys_section, content, flags=re.DOTALL, count=1)

    with open(KEYMAP_PATH, 'w') as f:
        f.write(new_content)
    
    print(f"Successfully updated {KEYMAP_PATH}")

if __name__ == "__main__":
    process()
