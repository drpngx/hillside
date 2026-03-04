# -*- coding: utf-8 -*-
import FreeCAD
import Part
import Mesh
import os

def manual_svg_top_view(shape, output_path, title):
    print(f"Generating manual top-view SVG for {title}...")
    try:
        bbox = shape.BoundBox
        print(f"BBox: {bbox}")
        
        # Determine SVG dimensions and scaling
        width, height = 1000, 1000
        margin = 50
        
        # Scaling to fit in 900x900
        dx = bbox.XMax - bbox.XMin
        dy = bbox.YMax - bbox.YMin
        scale = 900.0 / max(dx, dy, 1.0)
        
        cx, cy = bbox.Center.x, bbox.Center.y
        
        with open(output_path, "w") as f:
            f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
            f.write(f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" style="background:#fff">\n')
            f.write(f'  <text x="10" y="30" font-family="Arial" font-size="20">{title}</text>\n')
            f.write(f'  <text x="10" y="60" font-family="Arial" font-size="12">BBox: {bbox}</text>\n')
            # Flip Y for SVG (Y increases downwards in SVG)
            f.write(f'  <g transform="translate(500, 500) scale({scale}, {-scale}) translate({-cx}, {-cy})">\n')
            
            # Iterate over edges and draw them
            count = 0
            for edge in shape.Edges:
                # Discretize more for curves, less for lines
                # For a diagnostic, 5 points per edge is usually enough
                pts = edge.discretize(Number=10)
                if len(pts) > 1:
                    d = "M " + " L ".join([f"{p.x:.2f},{p.y:.2f}" for p in pts])
                    f.write(f'    <path d="{d}" fill="none" stroke="black" stroke-width="{0.5/scale}" />\n')
                    count += 1
            f.write('  </g>\n</svg>\n')
        print(f"Success: {output_path} ({count} edges drawn)")
    except Exception as e:
        print(f"Error generating SVG for {title}: {e}")

# 1. STL
stl_path = "/data/Hillside 52 Case - Top.stl"
if os.path.exists(stl_path):
    mesh = Mesh.read(stl_path)
    shape_stl = Part.Shape()
    shape_stl.makeShapeFromMesh(mesh.Topology, 0.1)
    manual_svg_top_view(shape_stl, "/data/view_stl_top.svg", "Original Left STL")

# 2. STEP
step_path = "/data/Hillside 52 Case - Combo.STEP"
if os.path.exists(step_path):
    shape_step = Part.read(step_path)
    manual_svg_top_view(shape_step, "/data/view_combo_top.svg", "Combo STEP Reference")
