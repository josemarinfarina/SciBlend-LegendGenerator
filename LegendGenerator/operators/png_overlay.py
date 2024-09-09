import bpy
import tempfile
import os
import numpy as np  
from bpy.props import IntProperty
from bpy.types import Operator
from ..utils.gradient_bar import create_gradient_bar
from ..utils.compositor_utils import update_legend_position_in_compositor, update_legend_scale_in_compositor
from ..utils.color_utils import load_colormaps, interpolate_color

class PNGOverlayOperator(Operator):
    bl_idname = "compositor.png_overlay"
    bl_label = "PNG Overlay Compositor"

    resolution: IntProperty(name="Resolution", default=1920)

    def execute(self, context):
        scene = context.scene
        
        if scene.colormap == 'CUSTOM':
            colors_values = scene.colors_values
            if not colors_values:
                color_nodes = [
                    (0.0, (0, 0, 0)),  
                    (1.0, (1, 1, 1)) 
                ]
                labels = ["0.00", "1.00"]
            else:
                color_nodes = []
                labels = []
                for i, item in enumerate(colors_values):
                    color_nodes.append((i / (len(colors_values) - 1), item.color[:3]))
                    labels.append(item.value)
        else:
            colormaps = load_colormaps()
            selected_colormap = colormaps.get(scene.colormap, [])
            print(f"Colormap seleccionado: {scene.colormap}")
            print(f"Datos del colormap: {selected_colormap[:5]}")
            
            start = scene.colormap_start
            end = scene.colormap_end
            subdivisions = scene.colormap_subdivisions
            
            positions = np.linspace(0, 1, subdivisions)
            values = np.linspace(start, end, subdivisions)
            
            color_nodes = []
            labels = []
            for pos, value in zip(positions, values):
                color = interpolate_color(selected_colormap, pos)
                color_nodes.append((pos, color))
                labels.append(f"{value:.2f}")
            
            print(f"Color nodes generados: {color_nodes[:5]}")

        if not color_nodes:
            self.report({'ERROR'}, "No color nodes available")
            return {'CANCELLED'}

        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
                tmpname = tmpfile.name
                font_type = scene.legend_font_type
                font_path = scene.legend_system_font if font_type == 'SYSTEM' else scene.legend_font
                
                print(f"Intentando crear la leyenda con la fuente: {font_path} (Tipo: {font_type})")
                create_gradient_bar(scene.legend_width, scene.legend_height, color_nodes,
                                    labels, tmpname, scene.legend_name, 
                                    scene.interpolation, scene.legend_orientation,
                                    font_type, font_path,
                                    scene.legend_text_color)  
            scene.use_nodes = True
            tree = scene.node_tree

            tree.nodes.clear()

            render_layers = tree.nodes.new('CompositorNodeRLayers')
            composite = tree.nodes.new('CompositorNodeComposite')
            alpha_over = tree.nodes.new('CompositorNodeAlphaOver')
            image_node = tree.nodes.new('CompositorNodeImage')
            scale_node = tree.nodes.new('CompositorNodeScale')
            translate_node = tree.nodes.new('CompositorNodeTranslate')

            try:
                image_node.image = bpy.data.images.load(tmpname)
            except:
                self.report({'ERROR'}, "Cannot load image")
                return {'CANCELLED'}

            scale_node.space = 'RELATIVE'
            scale_node.inputs['X'].default_value = scene.legend_scale_x
            scale_node.inputs['Y'].default_value = scene.legend_scale_y

            render_layers.location = (0, 0)
            image_node.location = (0, 200)
            scale_node.location = (200, 200)
            translate_node.location = (400, 200)
            alpha_over.location = (600, 0)
            composite.location = (800, 0)

            tree.links.new(render_layers.outputs["Image"], alpha_over.inputs[1])
            tree.links.new(image_node.outputs["Image"], scale_node.inputs["Image"])
            tree.links.new(scale_node.outputs["Image"], translate_node.inputs["Image"])
            tree.links.new(translate_node.outputs["Image"], alpha_over.inputs[2])
            tree.links.new(alpha_over.outputs["Image"], composite.inputs["Image"])

            update_legend_position_in_compositor(context)
            update_legend_scale_in_compositor(context)

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Error al generar la leyenda: {str(e)}")
            return {'CANCELLED'}

from ..utils.color_utils import interpolate_color