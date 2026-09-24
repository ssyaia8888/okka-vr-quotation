#!/usr/bin/env python3
"""
VR Quotation Blender Scene Generator
- 根據報價單資料自動生成專業 3D 場景
- 匯出 glTF 格式供 Three.js 載入
- 全本地運行，唔用收費模型
"""

import bpy
import bmesh
import json
import sys
import os
import math

def clear_scene():
    """清除預設場景"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    # 清除 materials
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)
    
    # 清除 meshes
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)

def create_material(name, color, roughness=0.5, metallic=0.0):
    """建立 PBR 材質"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # 清除預設 nodes
    for node in nodes:
        nodes.remove(node)
    
    # 建立 Principled BSDF
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    
    # 建立 Material Output
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (300, 0)
    
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    return mat

def create_room(width, depth, height, floor_color, wall_color, ceiling_color):
    """建立房間"""
    # 地板
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "Floor"
    floor.scale = (width/2, depth/2, 1)
    bpy.ops.object.transform_apply(scale=True)
    
    floor_mat = create_material("Floor_Material", floor_color, roughness=0.7)
    floor.data.materials.append(floor_mat)
    
    # 牆身 - 後牆
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -depth/2, height/2))
    back_wall = bpy.context.active_object
    back_wall.name = "Back_Wall"
    back_wall.rotation_euler = (0, 0, 0)
    back_wall.scale = (width/2, height/2, 1)
    bpy.ops.object.transform_apply(scale=True)
    
    wall_mat = create_material("Wall_Material", wall_color, roughness=0.85)
    back_wall.data.materials.append(wall_mat)
    
    # 牆身 - 左牆
    bpy.ops.mesh.primitive_plane_add(size=1, location=(-width/2, 0, height/2))
    left_wall = bpy.context.active_object
    left_wall.name = "Left_Wall"
    left_wall.rotation_euler = (0, math.pi/2, 0)
    left_wall.scale = (depth/2, height/2, 1)
    bpy.ops.object.transform_apply(scale=True)
    left_wall.data.materials.append(wall_mat)
    
    # 牆身 - 右牆（半透明）
    bpy.ops.mesh.primitive_plane_add(size=1, location=(width/2, 0, height/2))
    right_wall = bpy.context.active_object
    right_wall.name = "Right_Wall"
    right_wall.rotation_euler = (0, -math.pi/2, 0)
    right_wall.scale = (depth/2, height/2, 1)
    bpy.ops.object.transform_apply(scale=True)
    
    right_wall_mat = create_material("Right_Wall_Material", wall_color, roughness=0.85)
    right_wall_mat.blend_method = 'BLEND' if hasattr(right_wall_mat, 'blend_method') else None
    right_wall.data.materials.append(right_wall_mat)
    
    # 天花
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, height))
    ceiling = bpy.context.active_object
    ceiling.name = "Ceiling"
    ceiling.rotation_euler = (math.pi, 0, 0)
    ceiling.scale = (width/2, depth/2, 1)
    bpy.ops.object.transform_apply(scale=True)
    
    ceiling_mat = create_material("Ceiling_Material", ceiling_color, roughness=0.9)
    ceiling.data.materials.append(ceiling_mat)
    
    return floor, back_wall, left_wall, right_wall, ceiling

def create_sofa(location, color):
    """建立梳化"""
    sofa_mat = create_material("Sofa_Material", color, roughness=0.85)
    
    group = []
    
    # 座位
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    seat = bpy.context.active_object
    seat.name = "Sofa_Seat"
    seat.scale = (1.1, 0.45, 0.175)
    bpy.ops.object.transform_apply(scale=True)
    seat.data.materials.append(sofa_mat)
    group.append(seat)
    
    # 靠背
    bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0], location[1]-0.3, location[2]+0.25))
    back = bpy.context.active_object
    back.name = "Sofa_Back"
    back.scale = (1.1, 0.075, 0.25)
    bpy.ops.object.transform_apply(scale=True)
    back.data.materials.append(sofa_mat)
    group.append(back)
    
    # 左扶手
    bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0]-1.0, location[1], location[2]+0.15))
    left_arm = bpy.context.active_object
    left_arm.name = "Sofa_Left_Arm"
    left_arm.scale = (0.075, 0.45, 0.15)
    bpy.ops.object.transform_apply(scale=True)
    left_arm.data.materials.append(sofa_mat)
    group.append(left_arm)
    
    # 右扶手
    bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0]+1.0, location[1], location[2]+0.15))
    right_arm = bpy.context.active_object
    right_arm.name = "Sofa_Right_Arm"
    right_arm.scale = (0.075, 0.45, 0.15)
    bpy.ops.object.transform_apply(scale=True)
    right_arm.data.materials.append(sofa_mat)
    group.append(right_arm)
    
    # 坐墊
    cushion_mat = create_material("Cushion_Material", (0.35, 0.48, 0.6, 1), roughness=0.95)
    for i in [-0.35, 0, 0.35]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0]+i, location[1]+0.05, location[2]+0.2))
        cushion = bpy.context.active_object
        cushion.name = f"Sofa_Cushion_{i}"
        cushion.scale = (0.3, 0.25, 0.06)
        bpy.ops.object.transform_apply(scale=True)
        cushion.data.materials.append(cushion_mat)
        group.append(cushion)
    
    return group

def create_coffee_table(location, wood_color):
    """建立咖啡檯"""
    wood_mat = create_material("Table_Wood", wood_color, roughness=0.6, metallic=0.1)
    metal_mat = create_material("Table_Metal", (0.18, 0.18, 0.18, 1), roughness=0.3, metallic=0.8)
    
    group = []
    
    # 檯面
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    top = bpy.context.active_object
    top.name = "Coffee_Table_Top"
    top.scale = (0.5, 0.25, 0.02)
    bpy.ops.object.transform_apply(scale=True)
    top.data.materials.append(wood_mat)
    group.append(top)
    
    # 檯腳
    leg_geom = (0.015, 0.015, 0.2)
    for x in [-0.35, 0.35]:
        for z in [-0.15, 0.15]:
            bpy.ops.mesh.primitive_cylinder_add(radius=0.015, depth=0.4, location=(location[0]+x, location[1]+z, location[2]-0.2))
            leg = bpy.context.active_object
            leg.name = f"Table_Leg_{x}_{z}"
            leg.data.materials.append(metal_mat)
            group.append(leg)
    
    return group

def create_tv_cabinet(location, wood_color):
    """建立電視櫃"""
    dark_wood_mat = create_material("Cabinet_Dark_Wood", wood_color, roughness=0.5, metallic=0.1)
    metal_mat = create_material("Cabinet_Metal", (0.18, 0.18, 0.18, 1), roughness=0.3, metallic=0.8)
    
    group = []
    
    # 主體
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    body = bpy.context.active_object
    body.name = "TV_Cabinet_Body"
    body.scale = (0.9, 0.225, 0.25)
    bpy.ops.object.transform_apply(scale=True)
    body.data.materials.append(dark_wood_mat)
    group.append(body)
    
    # 抽屜
    drawer_mat = create_material("Drawer_Material", (0.29, 0.22, 0.16, 1), roughness=0.6)
    for i in [-0.55, 0, 0.55]:
        bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0]+i, location[1]+0.22, location[2]))
        drawer = bpy.context.active_object
        drawer.name = f"TV_Cabinet_Drawer_{i}"
        drawer.scale = (0.27, 0.01, 0.1)
        bpy.ops.object.transform_apply(scale=True)
        drawer.data.materials.append(drawer_mat)
        group.append(drawer)
        
        # 手柄
        bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0]+i, location[1]+0.23, location[2]))
        handle = bpy.context.active_object
        handle.name = f"TV_Cabinet_Handle_{i}"
        handle.scale = (0.075, 0.01, 0.01)
        bpy.ops.object.transform_apply(scale=True)
        handle.data.materials.append(metal_mat)
        group.append(handle)
    
    return group

def create_tv(location):
    """建立電視"""
    tv_mat = create_material("TV_Material", (0.1, 0.1, 0.1, 1), roughness=0.2, metallic=0.5)
    metal_mat = create_material("TV_Metal", (0.18, 0.18, 0.18, 1), roughness=0.3, metallic=0.8)
    
    group = []
    
    # 屏幕
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    screen = bpy.context.active_object
    screen.name = "TV_Screen"
    screen.scale = (0.7, 0.02, 0.4)
    bpy.ops.object.transform_apply(scale=True)
    screen.data.materials.append(tv_mat)
    group.append(screen)
    
    # 外框
    bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0], location[1]-0.01, location[2]))
    frame = bpy.context.active_object
    frame.name = "TV_Frame"
    frame.scale = (0.72, 0.01, 0.42)
    bpy.ops.object.transform_apply(scale=True)
    frame.data.materials.append(metal_mat)
    group.append(frame)
    
    # 底座
    bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=0.01, location=(location[0], location[1], location[2]-0.45))
    base = bpy.context.active_object
    base.name = "TV_Base"
    base.data.materials.append(metal_mat)
    group.append(base)
    
    return group

def create_floor_lamp(location):
    """建立落地燈"""
    metal_mat = create_material("Lamp_Metal", (0.18, 0.18, 0.18, 1), roughness=0.3, metallic=0.8)
    shade_mat = create_material("Lamp_Shade", (1.0, 0.96, 0.9, 1), roughness=0.9)
    
    group = []
    
    # 座
    bpy.ops.mesh.primitive_cylinder_add(radius=0.09, depth=0.02, location=location)
    base = bpy.context.active_object
    base.name = "Lamp_Base"
    base.data.materials.append(metal_mat)
    group.append(base)
    
    # 桿
    bpy.ops.mesh.primitive_cylinder_add(radius=0.008, depth=0.8, location=(location[0], location[1], location[2]+0.4))
    pole = bpy.context.active_object
    pole.name = "Lamp_Pole"
    pole.data.materials.append(metal_mat)
    group.append(pole)
    
    # 燈罩
    bpy.ops.mesh.primitive_cone_add(radius1=0.15, radius2=0.09, depth=0.15, location=(location[0], location[1], location[2]+0.85))
    shade = bpy.context.active_object
    shade.name = "Lamp_Shade"
    shade.data.materials.append(shade_mat)
    group.append(shade)
    
    return group

def create_rug(location, width, depth, color):
    """建立地毯"""
    rug_mat = create_material("Rug_Material", color, roughness=0.95)
    
    bpy.ops.mesh.primitive_plane_add(size=1, location=(location[0], location[1], 0.003))
    rug = bpy.context.active_object
    rug.name = "Rug"
    rug.scale = (width/2, depth/2, 1)
    bpy.ops.object.transform_apply(scale=True)
    rug.data.materials.append(rug_mat)
    
    return rug

def create_window(width, height, location, frame_color, glass_color):
    """建立窗戶"""
    frame_mat = create_material("Window_Frame", frame_color, roughness=0.3, metallic=0.5)
    glass_mat = create_material("Window_Glass", glass_color, roughness=0.1, metallic=0.1)
    
    group = []
    
    # 玻璃
    bpy.ops.mesh.primitive_plane_add(size=1, location=(location[0], location[1], location[2]+height/2))
    glass = bpy.context.active_object
    glass.name = "Window_Glass"
    glass.rotation_euler = (0, math.pi, 0)
    glass.scale = ((width-0.1)/2, (height-0.1)/2, 1)
    bpy.ops.object.transform_apply(scale=True)
    glass.data.materials.append(glass_mat)
    group.append(glass)
    
    # 窗框 - 上
    bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0], location[1], location[2]+height))
    top = bpy.context.active_object
    top.name = "Window_Frame_Top"
    top.scale = (width/2, 0.025, 0.025)
    bpy.ops.object.transform_apply(scale=True)
    top.data.materials.append(frame_mat)
    group.append(top)
    
    # 窗框 - 下
    bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0], location[1], location[2]))
    bottom = bpy.context.active_object
    bottom.name = "Window_Frame_Bottom"
    bottom.scale = (width/2, 0.025, 0.025)
    bpy.ops.object.transform_apply(scale=True)
    bottom.data.materials.append(frame_mat)
    group.append(bottom)
    
    # 窗框 - 左
    bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0]-width/2, location[1], location[2]+height/2))
    left = bpy.context.active_object
    left.name = "Window_Frame_Left"
    left.scale = (0.025, 0.025, height/2)
    bpy.ops.object.transform_apply(scale=True)
    left.data.materials.append(frame_mat)
    group.append(left)
    
    # 窗框 - 右
    bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0]+width/2, location[1], location[2]+height/2))
    right = bpy.context.active_object
    right.name = "Window_Frame_Right"
    right.scale = (0.025, 0.025, height/2)
    bpy.ops.object.transform_apply(scale=True)
    right.data.materials.append(frame_mat)
    group.append(right)
    
    # 窗框 - 中間
    bpy.ops.mesh.primitive_cube_add(size=1, location=(location[0], location[1], location[2]+height/2))
    center = bpy.context.active_object
    center.name = "Window_Frame_Center"
    center.scale = (0.025, 0.025, height/2)
    bpy.ops.object.transform_apply(scale=True)
    center.data.materials.append(frame_mat)
    group.append(center)
    
    return group

def setup_lighting():
    """設置專業燈光"""
    # 太陽光
    bpy.ops.object.light_add(type='SUN', location=(5, -5, 10))
    sun = bpy.context.active_object
    sun.name = "Sun_Light"
    sun.data.energy = 3.0
    sun.data.color = (1.0, 0.95, 0.9)
    
    # 半球光
    bpy.ops.object.light_add(type='AREA', location=(0, 0, 2.7))
    ambient = bpy.context.active_object
    ambient.name = "Ambient_Light"
    ambient.data.energy = 50.0
    ambient.data.size = 10.0
    ambient.data.color = (0.9, 0.95, 1.0)
    
    # 室內暖燈
    bpy.ops.object.light_add(type='POINT', location=(0, 0, 2.5))
    interior = bpy.context.active_object
    interior.name = "Interior_Light"
    interior.data.energy = 100.0
    interior.data.color = (1.0, 0.94, 0.87)
    interior.data.shadow_soft_size = 2.0
    
    return [sun, ambient, interior]

def setup_camera(width, depth, height):
    """設置相機"""
    bpy.ops.object.camera_add(location=(width*1.2, -depth*1.2, height*1.5))
    camera = bpy.context.active_object
    camera.name = "Main_Camera"
    
    # 朝向房間中心
    direction = camera.location
    camera.rotation_euler = (math.radians(60), 0, math.radians(45))
    
    bpy.context.scene.camera = camera
    
    return camera

def export_gltf(filepath):
    """匯出 glTF 格式"""
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format='GLB',
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials='EXPORT',
        export_cameras=True,
        export_lights=True
    )
    print(f"glTF exported to: {filepath}")

def main():
    """主函數"""
    # 讀取 JSON 參數 - 從環境變數
    params_json = os.environ.get('VR_SCENE_PARAMS', '')
    
    if params_json:
        params = json.loads(params_json)
    else:
        # 從檔案讀取
        params_file = os.environ.get('VR_SCENE_PARAMS_FILE', '/tmp/scene_params.json')
        if os.path.exists(params_file):
            with open(params_file) as f:
                params = json.load(f)
        else:
            # 預設值（測試用）
            params = {
                "room": {"width": 5, "depth": 4, "height": 2.8},
                "materials": {
                    "floor": {"color": [0.545, 0.451, 0.333, 1], "roughness": 0.7},
                    "wall": {"color": [0.96, 0.96, 0.86, 1], "roughness": 0.85},
                    "ceiling": {"color": [0.98, 0.98, 0.98, 1], "roughness": 0.9}
                },
                "furniture": True,
                "output": "/tmp/scene.glb"
            }
    
    room = params["room"]
    materials = params["materials"]
    output_path = params.get("output", "/tmp/scene.glb")
    
    print("=== VR Quotation Blender Scene Generator ===")
    print(f"Room: {room['width']}m x {room['depth']}m x {room['height']}m")
    
    # 清除場景
    clear_scene()
    
    # 建立房間
    floor_color = tuple(materials["floor"]["color"])
    wall_color = tuple(materials["wall"]["color"])
    ceiling_color = tuple(materials["ceiling"]["color"])
    
    create_room(
        room["width"], room["depth"], room["height"],
        floor_color, wall_color, ceiling_color
    )
    
    # 建立傢俬
    if params.get("furniture", True):
        sofa_color = (0.24, 0.35, 0.5, 1)
        create_sofa((-1, 1.2, 0.175), sofa_color)
        
        wood_color = (0.545, 0.271, 0.075, 1)
        create_coffee_table((-1, 0.4, 0.4), wood_color)
        create_tv_cabinet((-1, -1.5, 0.25), (0.24, 0.14, 0.08, 1))
        
        create_tv((-1, -1.5, 1.1))
        create_floor_lamp((1.5, 1.5, 0))
        
        create_rug((-0.8, 0.8), 2.5, 1.8, (0.42, 0.48, 0.55, 1))
        
        # 窗戶
        create_window(
            2.4, 1.5,
            (0, room["depth"]/2, 1.0),
            (1, 1, 1, 1),
            (0.53, 0.81, 0.92, 1)
        )
    
    # 燈光
    setup_lighting()
    
    # 相機
    setup_camera(room["width"], room["depth"], room["height"])
    
    # 匯出 glTF
    export_gltf(output_path)
    
    print("=== Scene generation complete ===")
    print(f"Output: {output_path}")

if __name__ == "__main__":
    main()
