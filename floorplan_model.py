#!/usr/bin/env python3
"""
Phase 5: Blender 自動化建模 — 匯入真實平面圖
- 讀取 SVG / JSON 平面圖
- 自動識別牆身、門、窗、房間
- 生成 3D 場景（牆身厚度、門窗開口）
- 匯出 glTF 供 Three.js 載入

用法:
  1. 準備平面圖 (SVG 或 JSON)
  2. 設定 VR_FLOORPLAN_FILE 環境變數
  3. 運行 blender_scene.py

JSON 平面圖格式:
{
  "rooms": [
    {
      "name": "Living Room",
      "walls": [[0,0],[5,0],[5,4],[0,4]],  # 頂點座標 (x, y) 單位米
      "doors": [{"from": [2,0], "width": 0.9}],
      "windows": [{"wall": 0, "position": 2.5, "width": 1.5, "height": 1.2, "sill": 0.9}]
    }
  ],
  "wall_thickness": 0.15,
  "wall_height": 2.8
}
"""

import bpy
import bmesh
import json
import os
import math
import re
from typing import List, Tuple, Dict, Any

# ============================================================
# 平面圖解析
# ============================================================

def parse_json_floorplan(filepath: str) -> Dict:
    """解析 JSON 平面圖"""
    with open(filepath) as f:
        data = json.load(f)
    # 驗證必要欄位
    assert "rooms" in data, "JSON 必須有 'rooms' 欄位"
    return data

def parse_svg_floorplan(filepath: str) -> Dict:
    """
    解析 SVG 平面圖（簡化版）
    識別:
    - <path> / <line> 作為牆身
    - 粗線 (stroke-width > 3) 作為牆身
    - 矩形作為門/窗
    """
    with open(filepath) as f:
        svg = f.read()

    rooms = []
    wall_thickness = 0.15
    wall_height = 2.8

    # 提取 viewBox 作為縮放參考
    vb_match = re.search(r'viewBox="([^"]+)"', svg)
    scale = 0.01  # 預設 1 unit = 1cm
    if vb_match:
        parts = vb_match.group(1).split()
        if len(parts) == 4:
            w, h = float(parts[2]), float(parts[3])
            # 假設平面圖最大 10m
            scale = 10.0 / max(w, h)

    # 提取 path 元素作為牆身
    paths = re.findall(r'<path[^>]*d="([^"]+)"[^>]*/?>', svg)
    lines = re.findall(r'<line[^>]*x1="([^"]+)"[^>]*y1="([^"]+)"[^>]*x2="([^"]+)"[^>]*y2="([^"]+)"', svg)

    # 簡化: 將所有 path/line 轉為牆身頂點
    wall_segments = []
    for x1, y1, x2, y2 in lines:
        wall_segments.append([
            [float(x1)*scale, float(y1)*scale],
            [float(x2)*scale, float(y2)*scale]
        ])

    if wall_segments:
        rooms.append({
            "name": "Main_Room",
            "walls": _segments_to_polygon(wall_segments),
            "doors": [],
            "windows": []
        })

    return {
        "rooms": rooms,
        "wall_thickness": wall_thickness,
        "wall_height": wall_height
    }

def _segments_to_polygon(segments: List[List[List[float]]]) -> List[List[float]]:
    """將線段集合轉為多邊形頂點（簡化: 取外框）"""
    # 收集所有頂點
    points = []
    for seg in segments:
        points.extend(seg)
    if not points:
        return [[0,0],[5,0],[5,4],[0,4]]
    # 簡單凸包（簡化版）
    return _convex_hull(points)

def _convex_hull(points: List[List[float]]) -> List[List[float]]:
    """簡化凸包算法"""
    if len(points) <= 3:
        return points
    points = sorted(set([tuple(p) for p in points]))
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [list(p) for p in (lower[:-1] + upper[:-1])]

def load_floorplan(filepath: str) -> Dict:
    """根據副檔名載入平面圖"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.json':
        return parse_json_floorplan(filepath)
    elif ext == '.svg':
        return parse_svg_floorplan(filepath)
    else:
        raise ValueError(f"唔支持嘅平面圖格式: {ext} (支持 .json, .svg)")

# ============================================================
# 3D 建模 — 牆身（帶厚度）
# ============================================================

def create_wall_from_segment(p1: Tuple, p2: Tuple, thickness: float, height: float,
                             door_openings: List[Dict] = None,
                             window_openings: List[Dict] = None):
    """
    根據線段建立 3D 牆身（帶厚度）
    """
    if door_openings is None:
        door_openings = []
    if window_openings is None:
        window_openings = []

    dx, dy = p2[0]-p1[0], p2[1]-p1[1]
    length = math.sqrt(dx*dx + dy*dy)
    if length < 0.01:
        return None

    # 牆身中心線
    cx, cy = (p1[0]+p2[0])/2, (p1[1]+p2[1])/2
    angle = math.atan2(dy, dx)

    # 建立牆身 mesh（箱體）
    mesh = bpy.data.meshes.new("Wall_Mesh")
    obj = bpy.data.objects.new("Wall", mesh)
    bpy.context.collection.objects.link(obj)

    # 基本箱體: 長 x 厚 x 高
    bm = bmesh.new()
    # 8 個頂點
    hx, hy, hz = length/2, thickness/2, height/2
    verts = []
    for sx in [-1, 1]:
        for sy in [-1, 1]:
            for sz in [-1, 1]:
                # 先建軸向箱體，之後旋轉
                verts.append(bm.verts.new((sx*hx, sy*hy, sz*hz)))

    # 建立 faces
    faces = [
        (0,1,3,2), (4,6,7,5),  # 前後
        (0,4,5,1), (2,3,7,6),  # 左右
        (0,2,6,4), (1,5,7,3)   # 上下
    ]
    for f in faces:
        try:
            bm.faces.new([verts[i] for i in f])
        except ValueError:
            pass

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    # 定位同旋轉
    obj.location = (cx, cy, height/2)
    obj.rotation_euler = (0, 0, angle)

    # 建立材質
    mat = bpy.data.materials.get("Wall_Material") or bpy.data.materials.new("Wall_Material")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.96, 0.96, 0.86, 1)
        bsdf.inputs['Roughness'].default_value = 0.85
    obj.data.materials.append(mat)

    # TODO: 門窗開口需要 boolean 切割（Phase 5 完整版）
    # 而家先建立完整牆身，門窗用獨立 object 表示

    return obj

def create_door_marker(position: Tuple, width: float, height: float, angle: float):
    """建立門（簡化: 用半透明平面表示開口）"""
    mat = bpy.data.materials.get("Door_Material") or bpy.data.materials.new("Door_Material")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.5, 0.3, 0.15, 1)
        bsdf.inputs['Roughness'].default_value = 0.6

    bpy.ops.mesh.primitive_plane_add(size=1, location=(position[0], position[1], height/2))
    door = bpy.context.active_object
    door.name = "Door"
    door.scale = (width/2, 0.05, 1)
    door.rotation_euler = (0, 0, angle)
    door.data.materials.append(mat)
    return door

def create_window_3d(position: Tuple, width: float, height: float, sill: float, angle: float):
    """建立窗戶（玻璃 + 窗框）"""
    glass_mat = bpy.data.materials.get("Window_Glass") or bpy.data.materials.new("Window_Glass")
    glass_mat.use_nodes = True
    bsdf = glass_mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (0.53, 0.81, 0.92, 1)
        bsdf.inputs['Roughness'].default_value = 0.1

    bpy.ops.mesh.primitive_plane_add(size=1, location=(position[0], position[1], sill + height/2))
    glass = bpy.context.active_object
    glass.name = "Window_Glass"
    glass.scale = (width/2, 0.03, 1)
    glass.rotation_euler = (0, 0, angle)
    glass.data.materials.append(glass_mat)
    return glass

# ============================================================
# 主函數 — 平面圖 → 3D 場景
# ============================================================

def build_scene_from_floorplan(filepath: str, output_path: str = "/tmp/scene.glb"):
    """從平面圖建立 3D 場景"""
    print(f"=== Phase 5: 匯入平面圖 {filepath} ===")

    # 載入平面圖
    plan = load_floorplan(filepath)
    wall_thickness = plan.get("wall_thickness", 0.15)
    wall_height = plan.get("wall_height", 2.8)

    # 清除場景
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # 建立地板
    all_x = [v[0] for r in plan["rooms"] for v in r["walls"]]
    all_y = [v[1] for r in plan["rooms"] for v in r["walls"]]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    floor_w, floor_d = max_x - min_x, max_y - min_y
    floor_cx, floor_cy = (min_x+max_x)/2, (min_y+max_y)/2

    bpy.ops.mesh.primitive_plane_add(size=1, location=(floor_cx, floor_cy, 0))
    floor = bpy.context.active_object
    floor.name = "Floor"
    floor.scale = (floor_w/2, floor_d/2, 1)
    bpy.ops.object.transform_apply(scale=True)
    floor_mat = bpy.data.materials.new("Floor_Material")
    floor_mat.use_nodes = True
    floor.data.materials.append(floor_mat)

    # 建立牆身
    for room in plan["rooms"]:
        walls = room["walls"]
        doors = room.get("doors", [])
        windows = room.get("windows", [])

        # 將每個牆線段轉為 3D 牆
        for i in range(len(walls)):
            p1 = walls[i]
            p2 = walls[(i+1) % len(walls)]
            # 識別呢面牆有冇門/窗
            wall_doors = [d for d in doors if _door_on_wall(d, p1, p2)]
            wall_windows = [w for w in windows if _window_on_wall(w, p1, p2)]

            create_wall_from_segment(
                (p1[0], p1[1]), (p2[0], p2[1]),
                wall_thickness, wall_height,
                wall_doors, wall_windows
            )

            # 建立門/窗 marker
            for d in wall_doors:
                pos = _point_on_wall(d.get("position", 0.5), p1, p2)
                angle = math.atan2(p2[1]-p1[1], p2[0]-p1[0])
                create_door_marker(pos, d.get("width", 0.9), wall_height*0.85, angle)

            for w in wall_windows:
                pos = _point_on_wall(w.get("position", 0.5), p1, p2)
                angle = math.atan2(p2[1]-p1[1], p2[0]-p1[0])
                create_window_3d(pos, w.get("width", 1.5), w.get("height", 1.2), w.get("sill", 0.9), angle)

    # 燈光
    bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
    sun = bpy.context.active_object
    sun.data.energy = 3.0

    bpy.ops.object.light_add(type='AREA', location=(floor_cx, floor_cy, wall_height))
    ambient = bpy.context.active_object
    ambient.data.energy = 50.0
    ambient.data.size = max(floor_w, floor_d)

    # 相機
    bpy.ops.object.camera_add(location=(floor_cx + floor_w*0.8, floor_cy - floor_d*0.8, wall_height*1.5))
    camera = bpy.context.active_object
    camera.rotation_euler = (math.radians(60), 0, math.radians(45))
    bpy.context.scene.camera = camera

    # 匯出
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format='GLB',
        export_apply=True,
        export_materials='EXPORT',
        export_cameras=True,
        export_lights=True
    )
    print(f"✅ glTF 匯出: {output_path}")
    return output_path

def _door_on_wall(door: Dict, p1: Tuple, p2: Tuple) -> bool:
    """檢查門係咪喺呢面牆"""
    pos = door.get("position", 0.5)
    if isinstance(pos, (list, tuple)) and len(pos) == 2:
        # 座標形式
        return _point_on_segment(pos, p1, p2)
    return True  # 比例形式，預設喺呢面牆

def _window_on_wall(win: Dict, p1: Tuple, p2: Tuple) -> bool:
    """檢查窗係咪喺呢面牆"""
    pos = win.get("position", 0.5)
    if isinstance(pos, (list, tuple)) and len(pos) == 2:
        return _point_on_segment(pos, p1, p2)
    return True

def _point_on_segment(point: Tuple, p1: Tuple, p2: Tuple, tolerance: float = 0.3) -> bool:
    """檢查點係咪喺線段附近"""
    dx, dy = p2[0]-p1[0], p2[1]-p1[1]
    length = math.sqrt(dx*dx + dy*dy)
    if length < 0.01:
        return False
    # 投影
    t = ((point[0]-p1[0])*dx + (point[1]-p1[1])*dy) / (length*length)
    t = max(0, min(1, t))
    proj = (p1[0]+t*dx, p1[1]+t*dy)
    dist = math.sqrt((point[0]-proj[0])**2 + (point[1]-proj[1])**2)
    return dist < tolerance

def _point_on_wall(t: float, p1: Tuple, p2: Tuple) -> Tuple:
    """取得線段上比例 t 嘅點"""
    return (p1[0] + t*(p2[0]-p1[0]), p1[1] + t*(p2[1]-p1[1]))

# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    filepath = os.environ.get('VR_FLOORPLAN_FILE', '/tmp/floorplan.json')
    output = os.environ.get('VR_SCENE_OUTPUT', '/tmp/scene.glb')

    if os.path.exists(filepath):
        build_scene_from_floorplan(filepath, output)
    else:
        print(f"⚠️ 平面圖檔案唔存在: {filepath}")
        print("使用預設測試平面圖...")
        # 預設測試: 5x4m 房間
        test_plan = {
            "rooms": [{
                "name": "Test_Room",
                "walls": [[0,0],[5,0],[5,4],[0,4]],
                "doors": [{"position": 2.5, "width": 0.9}],
                "windows": [{"position": 2.5, "width": 1.5, "height": 1.2, "sill": 0.9}]
            }],
            "wall_thickness": 0.15,
            "wall_height": 2.8
        }
        with open('/tmp/floorplan_test.json', 'w') as f:
            json.dump(test_plan, f)
        build_scene_from_floorplan('/tmp/floorplan_test.json', output)
