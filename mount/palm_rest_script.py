# -*- coding: utf-8 -*-
#
# FreeCAD Python Script to load Hillside 52 Case BASE and attach a palm rest
# USES ROBUST MESH OPERATIONS AND NORMAL HARMONIZATION
#
# podman run --rm -v "$(pwd)/mount:/data" docker.io/amrit3701/freecad-cli:latest FreeCADCmd /data/palm_rest_script.py
import FreeCAD
import Part
import Mesh
import math
import os

# ==============================================================================
# ==                           USER VARIABLES                                 ==
# ==============================================================================
input_stl = "/data/Hillside 52 Case - Base.stl"
output_left = "/data/Hillside 52 Case - Left - With Palm Rest.stl"
output_right = "/data/Hillside 52 Case - Right - With Palm Rest.stl"
output_svg = "/data/top_view_projection.svg"

# Target dimensions based on Combo.STEP
TARGET_X_INNER = 108.0
PALM_REST_THICKNESS = 30.0
# Reducing overlap to prevent material poking through thin walls
OVERLAP = 0.5 

# ==============================================================================
# ==                         HELPER FUNCTIONS                                 ==
# ==============================================================================

def get_clean_south_edge(mesh, samples=80):
    """Finds the southern-most points, ensuring we follow the outer skin"""
    bbox = mesh.BoundBox
    edge_points = []
    dx = (bbox.XMax - bbox.XMin) / float(samples)
    
    # We'll look at the southern-most 20% of the Y range to be very specific
    y_threshold = bbox.YMin + (bbox.YMax - bbox.YMin) * 0.2
    
    for i in range(samples + 1):
        x = bbox.XMin + i * dx
        min_y = 1e10
        found = False
        for p in mesh.Points:
            px, py = (p.Vector.x, p.Vector.y) if hasattr(p, 'Vector') else (p[0], p[1])
            if abs(px - x) < (dx * 0.51):
                if py < min_y and py < y_threshold:
                    min_y = py
                    found = True
        if found:
            edge_points.append(FreeCAD.Vector(x, min_y, 0))
    
    return edge_points

def create_palm_rest_solid(edge_pts, bbox):
    """Creates a dome-shaped palm rest solid (half-zeppelin)"""
    print("Generating domed palm rest solid...")
    
    # 1. Start with case edge (slight overlap)
    back_boundary = [p + FreeCAD.Vector(0, OVERLAP, 0) for p in edge_pts]
    
    # 2. Inner extension (X+)
    inner_y_back = back_boundary[-1].y
    inner_p_back = FreeCAD.Vector(TARGET_X_INNER, inner_y_back, 0)
    
    # 3. User-side boundary (South) - Profile based on Combo.STEP
    user_front = [
        FreeCAD.Vector(TARGET_X_INNER, -131.0, 0),
        FreeCAD.Vector(63.0, -150.0, 0),
        FreeCAD.Vector(0.0, -150.0, 0),
        FreeCAD.Vector(-20.0, -145.0, 0),
        FreeCAD.Vector(-45.0, -135.0, 0),
        FreeCAD.Vector(bbox.XMin + 2.0, -125.0, 0),
        FreeCAD.Vector(bbox.XMin, -110.0, 0)
    ]
    
    all_pts = back_boundary + [inner_p_back] + user_front + [back_boundary[0]]
    wire = Part.makePolygon(all_pts)
    face = Part.Face(wire)
    
    # 4. Create the Dome (Half-Zeppelin)
    # We use an ellipsoid (scaled sphere) and intersect it with the base footprint
    min_x = min(p.x for p in all_pts)
    max_x = max(p.x for p in all_pts)
    min_y = min(p.y for p in all_pts)
    max_y = max(p.y for p in all_pts)
    
    width = max_x - min_x
    depth = max_y - min_y
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    
    # Create sphere at origin
    sphere = Part.makeSphere(1.0)
    
    # Scale it to form an ellipsoid. 
    # The height (Z) will be PALM_REST_THICKNESS.
    # The X and Y radii should cover the boundary. 
    # Using 1.1x multiplier to ensure the curve covers the edges smoothly.
    s_x = (width / 2.0) * 1.1
    s_y = (depth / 2.0) * 1.1
    s_z = PALM_REST_THICKNESS
    
    mat = FreeCAD.Matrix()
    mat.scale(s_x, s_y, s_z)
    ellipsoid = sphere.transformGeometry(mat)
    
    # Move ellipsoid to center of the palm rest area (at Z=0)
    # The sphere starts at (0,0,0), so it spans [-s_z, s_z] in Z.
    ellipsoid.translate(FreeCAD.Vector(center_x, center_y, 0))
    
    # Create a tall extrusion of the base face to intersect with
    footprint = face.extrude(FreeCAD.Vector(0, 0, s_z * 2))
    
    # The intersection gives us the domed top half of the ellipsoid with the specified footprint
    solid = footprint.common(ellipsoid)
    
    # Z-Align: Put palm rest at the bottom of the case
    solid.translate(FreeCAD.Vector(0, 0, bbox.ZMin))
    
    print(f"Solid volume before drilling: {solid.Volume:.1f}")
    # 5. Drill Holes for M5 DIN 912 screws
    solid = drill_holes(solid, center_x, center_y, bbox.ZMin)
    print(f"Solid volume after drilling: {solid.Volume:.1f}")
    
    return solid

def drill_holes(solid, cx, cy, z_min):
    """Drills three M5 DIN 912 counterbored holes in an isolateral triangle"""
    print(f"Drilling vertical holes at center ({cx:.1f}, {cy:.1f})...")
    
    # Triangle vertices (Equilateral, side ~35mm)
    radius = 20.0 
    hole_pts = []
    for i in range(3):
        angle = math.radians(90 + i * 120)
        px = cx + radius * math.cos(angle)
        py = cy + radius * math.sin(angle)
        hole_pts.append(FreeCAD.Vector(px, py, z_min))

    # DIN 912 M5: Head Dia 8.5mm, Head Height 5mm, Screw Dia 5mm
    # Using 5.5mm for through hole and 10.0mm for counterbore
    # User requested ~6mm of material remaining ("length of hole")
    through_dia = 5.5
    cb_dia = 10.0
    flange_thickness = 6.0
    
    for p in hole_pts:
        # Through hole
        thru = Part.makeCylinder(through_dia/2.0, 100, p - FreeCAD.Vector(0,0,10))
        solid = solid.cut(thru)
        
        # Counterbore (from top down, leaving flange_thickness at bottom)
        cb = Part.makeCylinder(cb_dia/2.0, 100, p + FreeCAD.Vector(0,0,flange_thickness))
        solid = solid.cut(cb)
        
    return solid

# ==============================================================================
# ==                        MAIN PROCESS                                      ==
# ==============================================================================

print(f"Loading BASE STL: {input_stl}")
case_mesh = Mesh.read(input_stl)
bbox = case_mesh.BoundBox

# 1. Create Palm Rest
edge_pts = get_clean_south_edge(case_mesh)
palm_solid = create_palm_rest_solid(edge_pts, bbox)
palm_mesh = Mesh.Mesh(palm_solid.tessellate(0.1))

# 2. Combine Left
print("Assembling Left half...")
combined_left = case_mesh.copy()
combined_left.addMesh(palm_mesh)

# Cleanup mesh to prevent artifacts
combined_left.removeDuplicatedPoints()
combined_left.removeDuplicatedFacets()
combined_left.harmonizeNormals()

print(f"Writing: {output_left}")
combined_left.write(output_left)

# 3. Assemble Right
print("Mirroring for Right half...")
combined_right = combined_left.copy()
mat = FreeCAD.Matrix()
mat.scale(-1, 1, 1)
combined_right.transform(mat)
# Mirroring a mesh flips normals, MUST fix them or it looks like extra/ghost material
combined_right.flipNormals()
combined_right.harmonizeNormals()

print(f"Writing: {output_right}")
combined_right.write(output_right)

# 4. Top-View Projection using FreeCAD Kernel
print(f"Generating Verification SVG: {output_svg}")
try:
    # Slice the palm rest solid at Z=z_min+3 to see the M5 through-holes
    z_slice = bbox.ZMin + 3.0
    print(f"Slicing at Z={z_slice:.1f} for verification...")
    # slice(Normal, Distance) -> distance from origin along normal
    # The normal is (0,0,1), so distance is the Z value.
    section = palm_solid.slice(FreeCAD.Vector(0,0,1), z_slice)
    print(f"Slice edges count: {len(section)}")
    
    # Manual SVG drawing of PROJECTED CAD EDGES
    with open(output_svg, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
        f.write('<svg width="1000" height="1000" viewBox="-300 -400 600 600" xmlns="http://www.w3.org/2000/svg">\n')
        f.write('<g transform="scale(3, -3) translate(0, 50)">\n')
        # Add a light rectangle for the case boundary
        f.write(f'  <rect x="{bbox.XMin}" y="{bbox.YMin}" width="{bbox.XMax - bbox.XMin}" height="{bbox.YMax - bbox.YMin}" fill="none" stroke="gray" stroke-width="0.1" />\n')
        for edge in section:
            pts = edge.discretize(Number=40)
            if len(pts) > 1:
                d = "M " + " L ".join([f"{p.x:.2f},{p.y:.2f}" for p in pts])
                f.write(f'  <path d="{d}" fill="none" stroke="blue" stroke-width="0.1" />\n')
        f.write('</g></svg>\n')
    print("Success: Verification image generated.")
except Exception as e:
    print(f"Verification SVG failed: {e}")

print("\nPROCESS COMPLETE")
