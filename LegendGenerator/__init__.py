from bpy.props import IntProperty, FloatVectorProperty, CollectionProperty, StringProperty, EnumProperty
from bpy.types import Operator, Panel, PropertyGroup, UIList
import sys
import os
import tempfile
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import bpy

bl_info = {
    "name": "Legend Generator",
    "blender": (4, 2, 0),
    "category": "Compositing",
    "version": (1, 0, 0),
    "author": "José Marín",
    "description": "Customizable Legends for Scientific Visualization in Blender",
    "location": "View3D > UI > Legend Generator",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "support": "COMMUNITY",
}


def create_gradient_bar(resolution, color_nodes, labels, filename, legend_name, interpolation):
    fig, ax = plt.subplots(
        figsize=(resolution[0]/100, resolution[1]/100), dpi=100)
    ax.axis('off')

    positions = [pos for pos, _ in color_nodes]
    colors = [(r/255, g/255, b/255) for _, (r, g, b) in color_nodes]

    if interpolation == 'LINEAR':
        cmap = mcolors.LinearSegmentedColormap.from_list(
            'custom_cmap', list(zip(positions, colors)), N=256)
    elif interpolation == 'STAIRSTEP':
        cmap = mcolors.ListedColormap(colors)
    elif interpolation == 'CUBIC':
        cmap = mcolors.LinearSegmentedColormap.from_list(
            'custom_cmap', list(zip(positions, colors)), N=256, gamma=1.0)
    elif interpolation == 'NEAREST':
        cmap = mcolors.LinearSegmentedColormap.from_list(
            'custom_cmap', list(zip(positions, colors)), N=256, gamma=0.0)

    norm = mcolors.Normalize(vmin=0, vmax=100)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation='horizontal',
                        pad=0.1, aspect=20, fraction=0.05)
    cbar.set_label(legend_name, color='white')
    cbar.set_ticks(np.linspace(0, 100, len(labels)))
    cbar.set_ticklabels(labels)
    cbar.ax.xaxis.set_tick_params(color='white')
    cbar.ax.tick_params(labelcolor='white')

    plt.savefig(filename, format='png', bbox_inches='tight', transparent=True)
    plt.close(fig)


class ColorValue(PropertyGroup):
    color: FloatVectorProperty(
        name="Color",
        subtype='COLOR_GAMMA',
        size=3,
        default=(1.0, 1.0, 1.0)
    )
    value: StringProperty(name="Value", default="")


class ColorValues_UL_List(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        custom_icon = 'COLOR'
        split = layout.split(factor=0.3)
        split.prop(item, "value", text="", emboss=False, icon=custom_icon)
        split.prop(item, "color", text="")


class PNGOverlayOperator(Operator):
    bl_idname = "compositor.png_overlay"
    bl_label = "PNG Overlay Compositor"

    resolution: IntProperty(name="Resolution", default=1920)

    def execute(self, context):
        scene = context.scene
        colors_values = scene.colors_values

        color_nodes = []
        labels = []
        for i, item in enumerate(colors_values):
            color_nodes.append((i / (len(colors_values) - 1),
                               tuple(int(c * 255) for c in item.color)))
            labels.append(item.value)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
            tmpname = tmpfile.name
            create_gradient_bar((self.resolution, 1080), color_nodes,
                                labels, tmpname, scene.legend_name, scene.interpolation)

        scene.use_nodes = True
        tree = scene.node_tree

        tree.nodes.clear()

        render_layers = tree.nodes.new('CompositorNodeRLayers')
        composite = tree.nodes.new('CompositorNodeComposite')
        alpha_over = tree.nodes.new('CompositorNodeAlphaOver')
        image_node = tree.nodes.new('CompositorNodeImage')
        scale_node = tree.nodes.new('CompositorNodeScale')

        try:
            image_node.image = bpy.data.images.load(tmpname)
        except:
            self.report({'ERROR'}, "Cannot load image")
            return {'CANCELLED'}

        scale_node.space = 'RENDER_SIZE'

        render_layers.location = (0, 0)
        image_node.location = (0, 200)
        scale_node.location = (200, 200)
        alpha_over.location = (400, 0)
        composite.location = (600, 0)

        tree.links.new(render_layers.outputs["Image"], alpha_over.inputs[1])
        tree.links.new(image_node.outputs["Image"], scale_node.inputs["Image"])
        tree.links.new(scale_node.outputs["Image"], alpha_over.inputs[2])
        tree.links.new(alpha_over.outputs["Image"], composite.inputs["Image"])

        return {'FINISHED'}


class PNGOverlayPanel(Panel):
    bl_idname = "VIEW3D_PT_png_overlay"
    bl_label = "Legend Generator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Legend Generator"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.prop(scene, "num_nodes", text="Number of Nodes")
        layout.prop(scene, "legend_name", text="Legend Name")
        layout.prop(scene, "interpolation", text="Interpolation")

        row = layout.row()
        row.template_list("ColorValues_UL_List", "color_values_list",
                          scene, "colors_values", scene, "color_values_index")

        col = row.column(align=True)
        col.operator("scene.color_value_move", text="Up").direction = 'UP'
        col.operator("scene.color_value_move", text="Down").direction = 'DOWN'

        layout.operator("compositor.png_overlay",
                        text="Generate Legend and Add Overlay")


def update_nodes(self, context):
    scene = context.scene
    current_len = len(scene.colors_values)
    if scene.num_nodes > current_len:
        for i in range(scene.num_nodes - current_len):
            scene.colors_values.add()
    elif scene.num_nodes < current_len:
        for i in range(current_len - scene.num_nodes):
            scene.colors_values.remove(len(scene.colors_values) - 1)


class MoveColorValue(Operator):
    bl_idname = "scene.color_value_move"
    bl_label = "Move Color Value"

    direction: StringProperty()

    def execute(self, context):
        scene = context.scene
        index = scene.color_values_index

        if self.direction == 'UP' and index > 0:
            scene.colors_values.move(index, index-1)
            scene.color_values_index -= 1
        elif self.direction == 'DOWN' and index < len(scene.colors_values) - 1:
            scene.colors_values.move(index, index+1)
            scene.color_values_index += 1

        return {'FINISHED'}


def register():
    bpy.utils.register_class(ColorValue)
    bpy.utils.register_class(ColorValues_UL_List)
    bpy.utils.register_class(PNGOverlayOperator)
    bpy.utils.register_class(PNGOverlayPanel)
    bpy.utils.register_class(MoveColorValue)
    bpy.types.Scene.colors_values = CollectionProperty(type=ColorValue)
    bpy.types.Scene.num_nodes = IntProperty(
        name="Number of Nodes", default=2, min=2, update=update_nodes)
    bpy.types.Scene.color_values_index = IntProperty(default=-1)
    bpy.types.Scene.legend_name = StringProperty(
        name="Legend Name", default="Values")
    bpy.types.Scene.interpolation = EnumProperty(
        name="Interpolation",
        description="Color interpolation method",
        items=[
            ('LINEAR', "Gradient", "Linear interpolation between color nodes"),
            ('STAIRSTEP', "Stair Step", "Stair-step interpolation between color nodes"),
            ('CUBIC', "Cubic", "Cubic interpolation between color nodes"),
            ('NEAREST', "Nearest", "Nearest neighbor interpolation between color nodes")
        ],
        default='LINEAR'
    )


def unregister():
    bpy.utils.unregister_class(ColorValue)
    bpy.utils.unregister_class(ColorValues_UL_List)
    bpy.utils.unregister_class(PNGOverlayOperator)
    bpy.utils.unregister_class(PNGOverlayPanel)
    bpy.utils.unregister_class(MoveColorValue)
    del bpy.types.Scene.colors_values
    del bpy.types.Scene.num_nodes
    del bpy.types.Scene.color_values_index
    del bpy.types.Scene.legend_name
    del bpy.types.Scene.interpolation


if __name__ == "__main__":
    register()
