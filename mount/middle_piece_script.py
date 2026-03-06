# -*- coding: utf-8 -*-
#
# FreeCAD Python Script to generate a solid, rounded middle piece
#
# podman run --rm -v "$(pwd)/mount:/data" docker.io/amrit3701/freecad-cli:latest FreeCADCmd /data/middle_piece_script.py
import FreeCAD
import Part
import Mesh
import math

# ==============================================================================
# ==                           USER VARIABLES                                 ==
# ==============================================================================
output_stl = "/data/middle_piece.stl"
output_svg = "/data/middle_piece_view.svg"

BRIDGE_WIDTH = 50.0
BRIDGE_HEIGHT = 42.1
BRIDGE_DEPTH = 60.0   # Expanded to fit rotated holes
WALL_THICKNESS = 2.5  # Half thickness
FILLET_RADIUS = 1.0   # Scaled down to match thickness

TENTING_ANGLE = 20.0
TOE_IN_ANGLE = 15.0

HOLE_RADIUS = 20.0
THROUGH_DIA = 5.5

# ==============================================================================
# ==                         GEOMETRY FUNCTIONS                               ==
# ==============================================================================

def create_middle_piece():
    print(f"Generating solid middle piece (Thickness: {WALL_THICKNESS}mm)...")

    # 1. Precise Geometric Offset for the U-shape (XZ Plane)
    w_half = BRIDGE_WIDTH / 2.0
    h = BRIDGE_HEIGHT
    theta = math.radians(TENTING_ANGLE)

    # Outer Points
    foot_x = w_half + (h / math.tan(theta))
    p1 = FreeCAD.Vector(-foot_x, 0, 0)
    p2 = FreeCAD.Vector(-w_half, 0, h)
    p3 = FreeCAD.Vector(w_half, 0, h)
    p4 = FreeCAD.Vector(foot_x, 0, 0)

    # Inner Points (Computed for uniform thickness T)
    # The shift at the bridge corner uses the half-angle formula for a miter joint
    miter_shift = WALL_THICKNESS * math.tan(theta / 2.0)

    i1 = FreeCAD.Vector(-(foot_x - WALL_THICKNESS / math.sin(theta)), 0, 0)
    i2 = FreeCAD.Vector(-(w_half - miter_shift), 0, h - WALL_THICKNESS)
    i3 = FreeCAD.Vector(w_half - miter_shift, 0, h - WALL_THICKNESS)
    i4 = FreeCAD.Vector(foot_x - WALL_THICKNESS / math.sin(theta), 0, 0)

    all_pts = [p1, p2, p3, p4, i4, i3, i2, i1, p1]
    profile_face = Part.Face(Part.makePolygon(all_pts))

    # Verify Thickness (Area / centerline length)
    path_len = BRIDGE_WIDTH + 2 * (h / math.sin(theta))
    calc_thick = profile_face.Area / path_len
    print(f"Verified cross-section thickness: {calc_thick:.2f}mm")

    # 2. Extrude
    stand = profile_face.extrude(FreeCAD.Vector(0, BRIDGE_DEPTH, 0))
    stand = stand.removeSplitter()

    # 3. Round ONLY the 4 main long edges (Top and Bottom of the bridge)
    # This is much more stable than filleting every edge.
    print("Applying fillets to main edges...")
    fillet_edges = []
    for e in stand.Edges:
        if e.Length > (BRIDGE_DEPTH - 1.0):
            mid = e.CenterOfMass
            # Outer top edges
            if abs(mid.z - h) < 0.1 and abs(abs(mid.x) - w_half) < 0.1:
                fillet_edges.append(e)
            # Outer bottom "feet" edges
            if abs(mid.z) < 0.1 and abs(abs(mid.x) - foot_x) < 0.1:
                fillet_edges.append(e)

    if fillet_edges:
        try:
            stand = stand.makeFillet(FILLET_RADIUS, fillet_edges)
        except:
            print("Fillet failed, skipping...")

    # 4. Drill holes
    def drill_holes(solid, is_left):
        side = -1.0 if is_left else 1.0
        # Position on the leg
        leg_len = h / math.sin(theta)
        hole_dist_down = leg_len - 32.9  # Keep holes close to the edge of the sides

        # Calculate base hole positions
        holes = []
        for i in range(3):
            angle = math.radians(90 + i * 120)
            hx = HOLE_RADIUS * math.cos(angle)
            hy = HOLE_RADIUS * math.sin(angle)
            holes.append((hx, hy))

        # Find center of rotation (hole furthermost from middle)
        if side == -1.0:
            cx, cy = min(holes, key=lambda p: p[0])
        else:
            cx, cy = max(holes, key=lambda p: p[0])

        # Apply 35 deg rotation (CW for left, CCW for right)
        rot_angle = math.radians(-35 * -side)
        cos_a = math.cos(rot_angle)
        sin_a = math.sin(rot_angle)

        rotated_holes = []
        for hx, hy in holes:
            nx = cx + (hx - cx) * cos_a - (hy - cy) * sin_a
            ny = cy + (hx - cx) * sin_a + (hy - cy) * cos_a
            rotated_holes.append((nx, ny))

        # Re-center rotated holes to avoid edges
        min_x = min(p[0] for p in rotated_holes)
        max_x = max(p[0] for p in rotated_holes)
        min_y = min(p[1] for p in rotated_holes)
        max_y = max(p[1] for p in rotated_holes)

        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0

        holes_union = None
        for nx, ny in rotated_holes:
            sx = nx - center_x
            sy = ny - center_y

            h_cyl = Part.makeCylinder(THROUGH_DIA/2.0, 100, FreeCAD.Vector(sx, sy, -50))
            if holes_union is None: holes_union = h_cyl
            else: holes_union = holes_union.fuse(h_cyl)
        holes_union.rotate(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), -side * TOE_IN_ANGLE)
        holes_union.rotate(FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,1,0), side * TENTING_ANGLE)

        off_x = side * (w_half + hole_dist_down * math.cos(theta))
        off_z = h - hole_dist_down * math.sin(theta)
        holes_union.translate(FreeCAD.Vector(off_x, BRIDGE_DEPTH/2.0, off_z))

        return solid.cut(holes_union)

    stand = drill_holes(stand, True)
    stand = drill_holes(stand, False)

    return stand

# ==============================================================================
# ==                        MAIN PROCESS                                      ==
# ==============================================================================

middle_solid = create_middle_piece()
middle_mesh = Mesh.Mesh(middle_solid.tessellate(0.1))

print(f"Writing: {output_stl}")
middle_mesh.write(output_stl)

# Multi-View SVG
print(f"Generating Multi-View SVG: {output_svg}")
try:
    with open(output_svg, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
        f.write('<svg width="1000" height="1000" viewBox="0 0 1000 1000" xmlns="http://www.w3.org/2000/svg">\n')
        f.write('<rect width="1000" height="1000" fill="white" />\n')

        def draw_view(view_vec, x_off, y_off, label):
            proj = middle_solid.project(view_vec)
            f.write(f'<text x="{x_off}" y="{y_off-10}" font-family="Arial" font-size="20">{label}</text>\n')
            f.write(f'<g transform="translate({x_off+150}, {y_off+150}) scale(3, -3)">\n')
            for edge in proj.Edges:
                pts = edge.discretize(Number=40)
                if len(pts) > 1:
                    d = "M " + " L ".join([f"{p.x:.2f},{p.y:.2f}" for p in pts])
                    f.write(f'  <path d="{d}" fill="none" stroke="black" stroke-width="0.2" />\n')
            f.write('</g>\n')

        draw_view(FreeCAD.Vector(0, -1, 0), 50, 50, "Front View (XZ)")
        draw_view(FreeCAD.Vector(0, 0, 1), 450, 50, "Top View (XY)")
        draw_view(FreeCAD.Vector(1, -1, 1), 250, 450, "Perspective View")
        f.write('</svg>\n')
except Exception as e:
    print(f"Verification SVG failed: {e}")

print("\nPROCESS COMPLETE")
