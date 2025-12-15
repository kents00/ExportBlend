from bpy.props import StringProperty, BoolProperty, EnumProperty
import os
import bpy
bl_info = {
    "name": "ExportBlend",
    "author": "Kent Edoloverio",
    "version": (1, 2, 0),
    "blender": (4, 0, 0),
    "location": "Node Editor > Sidebar > Export Tab",
    "description": "Export node groups to Python code with one click",
    "category": "Node",
}


def get_socket_type(socket):
    """Get the socket type string for the API."""
    socket_type_map = {
        'VALUE': 'NodeSocketFloat',
        'INT': 'NodeSocketInt',
        'BOOLEAN': 'NodeSocketBool',
        'VECTOR': 'NodeSocketVector',
        'RGBA': 'NodeSocketColor',
        'STRING': 'NodeSocketString',
        'SHADER': 'NodeSocketShader',
        'OBJECT': 'NodeSocketObject',
        'IMAGE': 'NodeSocketImage',
        'GEOMETRY': 'NodeSocketGeometry',
        'COLLECTION': 'NodeSocketCollection',
        'MATERIAL': 'NodeSocketMaterial',
        'TEXTURE': 'NodeSocketTexture',
        'ROTATION': 'NodeSocketRotation',
        'MENU': 'NodeSocketMenu',
    }

    if hasattr(socket, 'type'):
        return socket_type_map.get(socket.type, 'NodeSocketFloat')
    return 'NodeSocketFloat'


def format_value(val):
    """Format a value as valid Python code."""
    if val is None:
        return None

    if isinstance(val, str):
        return repr(val)

    if isinstance(val, bool):
        return repr(val)
    if isinstance(val, int):
        return repr(val)
    if isinstance(val, float):
        return repr(val)

    type_name = type(val).__name__
    if type_name in ('Vector', 'Color', 'Euler', 'Quaternion'):
        return repr(tuple(val))

    if hasattr(val, '__iter__'):
        try:
            items = list(val)
            if items and all(isinstance(item, str) and len(item) == 1 for item in items):
                return None
            return repr(tuple(items))
        except:
            return None

    return repr(val)


def get_socket_default_value(socket):
    """Get the default value of a socket as a string."""
    if not hasattr(socket, 'default_value'):
        return None

    val = socket.default_value
    return format_value(val)


def sanitize_name(name):
    """Convert a name to a valid Python variable name."""
    result = ""
    for i, char in enumerate(name):
        if char.isalnum() or char == '_':
            result += char
        else:
            result += '_'

    if result and result[0].isdigit():
        result = '_' + result

    if not result:
        result = "node"

    return result.lower()


def get_node_tree_type(node_tree):
    """Determine the node tree type."""
    tree_type = node_tree.bl_idname
    if tree_type == 'ShaderNodeTree':
        return 'ShaderNodeTree'
    elif tree_type == 'GeometryNodeTree':
        return 'GeometryNodeTree'
    elif tree_type == 'CompositorNodeTree':
        return 'CompositorNodeTree'
    elif tree_type == 'TextureNodeTree':
        return 'TextureNodeTree'
    return tree_type


SKIP_PROPS = {
    'name', 'label', 'location', 'width', 'width_hidden', 'height',
    'dimensions', 'type', 'bl_idname', 'bl_label', 'bl_description',
    'bl_icon', 'bl_static_type', 'bl_width_default', 'bl_width_min',
    'bl_width_max', 'bl_height_default', 'bl_height_min', 'bl_height_max',
    'color', 'use_custom_color', 'select', 'show_options', 'show_preview',
    'hide', 'mute', 'show_texture', 'inputs', 'outputs', 'internal_links',
    'parent', 'rna_type', 'is_registered_node_type', 'location_absolute',
    'warning_propagation', 'is_active_output'
}


def find_nested_node_groups(node_group, visited=None):
    """Recursively find all nested node groups used within a node group."""
    if visited is None:
        visited = set()

    nested_groups = []

    # Avoid circular dependencies
    if node_group.name in visited:
        return nested_groups

    visited.add(node_group.name)

    for node in node_group.nodes:
        # Check if node is a group node with a node_tree assigned
        if node.bl_idname in ('GeometryNodeGroup', 'ShaderNodeGroup', 'CompositorNodeGroup', 'TextureNodeGroup'):
            if hasattr(node, 'node_tree') and node.node_tree:
                nested_tree = node.node_tree
                # Recursively find nested groups within this group
                sub_nested = find_nested_node_groups(nested_tree, visited)
                # Add sub-nested groups first (dependencies)
                for sub_group in sub_nested:
                    if sub_group not in nested_groups:
                        nested_groups.append(sub_group)
                # Then add this group
                if nested_tree not in nested_groups:
                    nested_groups.append(nested_tree)

    return nested_groups


def export_single_node_group(node_group):
    """Export a single node group definition without dependencies or main execution code."""
    lines = []

    func_name = sanitize_name(node_group.name)
    tree_type = get_node_tree_type(node_group)

    lines.append(f"def create_{func_name}_node_group():")
    lines.append(f'    """Create the {node_group.name} node group."""')
    lines.append("")
    lines.append(f'    # Check if node group already exists')
    lines.append(f'    if "{node_group.name}" in bpy.data.node_groups:')
    lines.append(f'        return bpy.data.node_groups["{node_group.name}"]')
    lines.append("")
    lines.append(f'    # Create new node group')
    lines.append(
        f'    node_group = bpy.data.node_groups.new(name="{node_group.name}", type=\'{tree_type}\')')
    lines.append("")

    # Export interface (inputs and outputs) for Blender 4.0+
    if hasattr(node_group, 'interface'):
        lines.append("    # Create group interface (sockets)")
        for item in node_group.interface.items_tree:
            if item.item_type == 'SOCKET':
                socket_type = item.socket_type
                in_out = 'INPUT' if item.in_out == 'INPUT' else 'OUTPUT'
                lines.append(
                    f'    node_group.interface.new_socket(name="{item.name}", in_out=\'{in_out}\', socket_type=\'{socket_type}\')')
        lines.append("")

    # Export nodes
    lines.append("    # Create nodes")
    node_var_names = {}

    for i, node in enumerate(node_group.nodes):
        var_name = f"node_{i}_{sanitize_name(node.name)}"
        node_var_names[node.name] = var_name

        lines.append(f'    # Node: {node.name}')
        lines.append(
            f'    {var_name} = node_group.nodes.new(type=\'{node.bl_idname}\')')
        lines.append(f'    {var_name}.name = "{node.name}"')
        lines.append(f'    {var_name}.label = "{node.label}"')
        lines.append(
            f'    {var_name}.location = ({node.location.x:.1f}, {node.location.y:.1f})')

        if hasattr(node, 'width'):
            lines.append(f'    {var_name}.width = {node.width:.1f}')

        if node.hide:
            lines.append(f'    {var_name}.hide = True')

        if node.mute:
            lines.append(f'    {var_name}.mute = True')

        # Export node-specific properties
        export_node_properties(lines, node, var_name)

        # Export input socket default values
        for j, input_socket in enumerate(node.inputs):
            if hasattr(input_socket, 'default_value') and not input_socket.is_linked:
                default_val = get_socket_default_value(input_socket)
                if default_val is not None:
                    lines.append(
                        f'    if len({var_name}.inputs) > {j} and hasattr({var_name}.inputs[{j}], "default_value"):')
                    lines.append(f'        try:')
                    lines.append(
                        f'            {var_name}.inputs[{j}].default_value = {default_val}')
                    lines.append(f'        except:')
                    lines.append(f'            pass')

        lines.append("")

    # Export links
    lines.append("    # Create links")
    for link in node_group.links:
        from_node_var = node_var_names.get(link.from_node.name)
        to_node_var = node_var_names.get(link.to_node.name)

        if from_node_var and to_node_var:
            from_socket_index = list(
                link.from_node.outputs).index(link.from_socket)
            to_socket_index = list(link.to_node.inputs).index(link.to_socket)

            lines.append(
                f'    node_group.links.new({from_node_var}.outputs[{from_socket_index}], {to_node_var}.inputs[{to_socket_index}])')

    lines.append("")
    lines.append("    return node_group")
    lines.append("")

    return "\n".join(lines)


def export_node_group_to_python(node_group, auto_assign=True, include_nested=True):
    """Export a node group to Python code."""

    lines = []
    lines.append("import bpy")
    lines.append("")
    lines.append("")

    # Find and export nested node groups first (if enabled)
    nested_groups = find_nested_node_groups(
        node_group) if include_nested else []
    if nested_groups:
        lines.append("# === Nested Node Groups (Dependencies) ===")
        lines.append("")
        for nested_group in nested_groups:
            lines.extend(export_single_node_group(nested_group).split('\n'))
            lines.append("")
        lines.append("# === Main Node Group ===")
        lines.append("")

    func_name = sanitize_name(node_group.name)
    tree_type = get_node_tree_type(node_group)

    lines.append(f"def create_{func_name}_node_group():")
    lines.append(f'    """Create the {node_group.name} node group."""')
    lines.append("")
    lines.append(f'    # Check if node group already exists')
    lines.append(f'    if "{node_group.name}" in bpy.data.node_groups:')
    lines.append(f'        return bpy.data.node_groups["{node_group.name}"]')
    lines.append("")
    lines.append(f'    # Create new node group')
    lines.append(
        f'    node_group = bpy.data.node_groups.new(name="{node_group.name}", type=\'{tree_type}\')')
    lines.append("")

    # Export interface (inputs and outputs) for Blender 4.0+
    if hasattr(node_group, 'interface'):
        lines.append("    # Create group interface (sockets)")
        for item in node_group.interface.items_tree:
            if item.item_type == 'SOCKET':
                socket_type = item.socket_type
                in_out = 'INPUT' if item.in_out == 'INPUT' else 'OUTPUT'
                lines.append(
                    f'    node_group.interface.new_socket(name="{item.name}", in_out=\'{in_out}\', socket_type=\'{socket_type}\')')
        lines.append("")

    # Export nodes
    lines.append("    # Create nodes")
    node_var_names = {}

    for i, node in enumerate(node_group.nodes):
        var_name = f"node_{i}_{sanitize_name(node.name)}"
        node_var_names[node.name] = var_name

        lines.append(f'    # Node: {node.name}')
        lines.append(
            f'    {var_name} = node_group.nodes.new(type=\'{node.bl_idname}\')')
        lines.append(f'    {var_name}.name = "{node.name}"')
        lines.append(f'    {var_name}.label = "{node.label}"')
        lines.append(
            f'    {var_name}.location = ({node.location.x:.1f}, {node.location.y:.1f})')

        if hasattr(node, 'width'):
            lines.append(f'    {var_name}.width = {node.width:.1f}')

        if node.hide:
            lines.append(f'    {var_name}.hide = True')

        if node.mute:
            lines.append(f'    {var_name}.mute = True')

        # Export node-specific properties
        export_node_properties(lines, node, var_name)

        # Export input socket default values
        for j, input_socket in enumerate(node.inputs):
            if hasattr(input_socket, 'default_value') and not input_socket.is_linked:
                default_val = get_socket_default_value(input_socket)
                if default_val is not None:
                    lines.append(
                        f'    if len({var_name}.inputs) > {j} and hasattr({var_name}.inputs[{j}], "default_value"):')
                    lines.append(f'        try:')
                    lines.append(
                        f'            {var_name}.inputs[{j}].default_value = {default_val}')
                    lines.append(f'        except:')
                    lines.append(f'            pass')

        lines.append("")

    # Export links
    lines.append("    # Create links")
    for link in node_group.links:
        from_node_var = node_var_names.get(link.from_node.name)
        to_node_var = node_var_names.get(link.to_node.name)

        if from_node_var and to_node_var:
            from_socket_index = list(
                link.from_node.outputs).index(link.from_socket)
            to_socket_index = list(link.to_node.inputs).index(link.to_socket)

            lines.append(
                f'    node_group.links.new({from_node_var}.outputs[{from_socket_index}], {to_node_var}.inputs[{to_socket_index}])')

    lines.append("")
    lines.append("    return node_group")
    lines.append("")
    lines.append("")

    # Add helper function to assign to object (if main or any nested is GeometryNodeTree)
    has_geometry_nodes = tree_type == 'GeometryNodeTree' or any(
        get_node_tree_type(ng) == 'GeometryNodeTree' for ng in nested_groups
    )

    if has_geometry_nodes and auto_assign:
        lines.append(
            f"def assign_to_object(node_group, obj=None, create_if_none=True):")
        lines.append(f'    """Assign the geometry node group to an object."""')
        lines.append(f'    ')
        lines.append(
            f'    # If no object provided, try to use active object or create new one')
        lines.append(f'    if obj is None:')
        lines.append(f'        obj = bpy.context.active_object')
        lines.append(f'    ')
        lines.append(f'    if obj is None and create_if_none:')
        lines.append(f'        # Create a new mesh object')
        lines.append(
            f'        mesh = bpy.data.meshes.new(node_group.name + "_mesh")')
        lines.append(
            f'        obj = bpy.data.objects.new(node_group.name + "_object", mesh)')
        lines.append(f'        bpy.context.collection.objects.link(obj)')
        lines.append(f'        bpy.context.view_layer.objects.active = obj')
        lines.append(f'        obj.select_set(True)')
        lines.append(f'    ')
        lines.append(f'    if obj is None:')
        lines.append(
            f'        print("No object available to assign the node group to.")')
        lines.append(f'        return None')
        lines.append(f'    ')
        lines.append(
            f'    # Check if object already has a Geometry Nodes modifier with this node group')
        lines.append(f'    for mod in obj.modifiers:')
        lines.append(
            f'        if mod.type == "NODES" and mod.node_group == node_group:')
        lines.append(
            f'            print(f"Object \'{{obj.name}}\' already has this node group assigned.")')
        lines.append(f'            return mod')
        lines.append(f'    ')
        lines.append(f'    # Add new Geometry Nodes modifier')
        lines.append(
            f'    mod = obj.modifiers.new(name=node_group.name, type="NODES")')
        lines.append(f'    mod.node_group = node_group')
        lines.append(f'    ')
        lines.append(
            f'    print(f"Assigned \'{{node_group.name}}\' to object \'{{obj.name}}\'")')
        lines.append(f'    return mod')
        lines.append("")
        lines.append("")

    # Add helper function to assign shader to material
    if tree_type == 'ShaderNodeTree' and auto_assign:
        lines.append(
            f"def assign_to_material(node_group, mat=None, create_if_none=True):")
        lines.append(f'    """Assign the shader node group to a material."""')
        lines.append(f'    ')
        lines.append(
            f'    # If no material provided, try to use active material or create new one')
        lines.append(f'    if mat is None:')
        lines.append(f'        # Try to get material from active object')
        lines.append(f'        obj = bpy.context.active_object')
        lines.append(f'        if obj and obj.active_material:')
        lines.append(f'            mat = obj.active_material')
        lines.append(f'    ')
        lines.append(f'    if mat is None and create_if_none:')
        lines.append(f'        # Create a new material')
        lines.append(
            f'        mat = bpy.data.materials.new(name=node_group.name + "_material")')
        lines.append(f'        mat.use_nodes = True')
        lines.append(f'        # Assign to active object if available')
        lines.append(f'        obj = bpy.context.active_object')
        lines.append(f'        if obj:')
        lines.append(f'            if len(obj.data.materials) > 0:')
        lines.append(f'                obj.data.materials[0] = mat')
        lines.append(f'            else:')
        lines.append(f'                obj.data.materials.append(mat)')
        lines.append(f'    ')
        lines.append(f'    if mat is None:')
        lines.append(
            f'        print("No material available to assign the node group to.")')
        lines.append(f'        return None')
        lines.append(f'    ')
        lines.append(f'    if not mat.use_nodes:')
        lines.append(f'        mat.use_nodes = True')
        lines.append(f'    ')
        lines.append(
            f'    # Add the node group as a single group node (not expanded)')
        lines.append(f'    nodes = mat.node_tree.nodes')
        lines.append(f'    group_node = nodes.new(type="ShaderNodeGroup")')
        lines.append(f'    group_node.node_tree = node_group')
        lines.append(f'    group_node.name = node_group.name')
        lines.append(f'    group_node.location = (-200, 300)')
        lines.append(f'    ')
        lines.append(f'    # Optionally connect to Material Output if present')
        lines.append(f'    output_node = None')
        lines.append(f'    for node in nodes:')
        lines.append(f'        if node.type == "OUTPUT_MATERIAL":')
        lines.append(f'            output_node = node')
        lines.append(f'            break')
        lines.append(f'    ')
        lines.append(f'    if output_node and len(group_node.outputs) > 0:')
        lines.append(f'        # Connect first output to Surface input')
        lines.append(
            f'        mat.node_tree.links.new(group_node.outputs[0], output_node.inputs[0])')
        lines.append(f'    ')
        lines.append(
            f'    print(f"Added shader node group \'{{node_group.name}}\' to material \'{{mat.name}}\'")')
        lines.append(f'    return group_node')
        lines.append("")
        lines.append("")

    # Main execution
    if nested_groups:
        lines.append("# Create nested node groups first")
        for nested_group in nested_groups:
            nested_func_name = sanitize_name(nested_group.name)
            lines.append(
                f"{nested_func_name}_group = create_{nested_func_name}_node_group()")
            lines.append(
                f'print(f"Created nested node group: {nested_group.name}")')
        lines.append("")

    lines.append(f"# Create the main node group")
    lines.append(f"node_group = create_{func_name}_node_group()")
    lines.append(
        f'print(f"Node group \\"{node_group.name}\\" created successfully!")')

    if tree_type == 'GeometryNodeTree' and auto_assign:
        lines.append("")
        lines.append(
            "# Assign to object (creates new object if none selected)")
        lines.append(
            "# Set create_if_none=False if you only want to assign to existing selected object")
        lines.append(
            "modifier = assign_to_object(node_group, obj=None, create_if_none=True)")
        lines.append("")
        lines.append("# To assign to a specific existing object, use:")
        lines.append(
            "# modifier = assign_to_object(node_group, obj=bpy.data.objects['YourObjectName'], create_if_none=False)")

    elif tree_type == 'ShaderNodeTree' and auto_assign:
        lines.append("")
        lines.append(
            "# Assign to material (creates new material if none available)")
        lines.append(
            "# Set create_if_none=False if you only want to assign to existing material")
        lines.append(
            "material = assign_to_material(node_group, mat=None, create_if_none=True)")
        lines.append("")
        lines.append("# To assign to a specific existing material, use:")
        lines.append(
            "# material = assign_to_material(node_group, mat=bpy.data.materials['YourMaterialName'], create_if_none=False)")

    return "\n".join(lines)


def export_node_properties(lines, node, var_name):
    """Export node-specific properties."""

    if node.bl_idname == 'ShaderNodeMath':
        lines.append(f'    {var_name}.operation = \'{node.operation}\'')
        if hasattr(node, 'use_clamp'):
            lines.append(f'    {var_name}.use_clamp = {node.use_clamp}')

    elif node.bl_idname == 'ShaderNodeVectorMath':
        lines.append(f'    {var_name}.operation = \'{node.operation}\'')

    elif node.bl_idname == 'ShaderNodeMix':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')
        lines.append(f'    {var_name}.blend_type = \'{node.blend_type}\'')
        lines.append(f'    {var_name}.clamp_factor = {node.clamp_factor}')
        lines.append(f'    {var_name}.clamp_result = {node.clamp_result}')

    elif node.bl_idname == 'ShaderNodeMixRGB':
        lines.append(f'    {var_name}.blend_type = \'{node.blend_type}\'')
        lines.append(f'    {var_name}.use_clamp = {node.use_clamp}')

    elif node.bl_idname == 'ShaderNodeMapRange':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')
        lines.append(
            f'    {var_name}.interpolation_type = \'{node.interpolation_type}\'')
        lines.append(f'    {var_name}.clamp = {node.clamp}')

    elif node.bl_idname == 'ShaderNodeValToRGB':
        lines.append(f'    # Color Ramp settings')
        lines.append(
            f'    {var_name}.color_ramp.color_mode = \'{node.color_ramp.color_mode}\'')
        lines.append(
            f'    {var_name}.color_ramp.interpolation = \'{node.color_ramp.interpolation}\'')

        elements = node.color_ramp.elements
        lines.append(f'    # Remove default elements and add new ones')
        lines.append(f'    while len({var_name}.color_ramp.elements) > 1:')
        lines.append(
            f'        {var_name}.color_ramp.elements.remove({var_name}.color_ramp.elements[0])')

        for k, elem in enumerate(elements):
            if k == 0:
                lines.append(
                    f'    {var_name}.color_ramp.elements[0].position = {elem.position}')
                lines.append(
                    f'    {var_name}.color_ramp.elements[0].color = {tuple(elem.color)}')
            else:
                lines.append(
                    f'    elem_{k} = {var_name}.color_ramp.elements.new({elem.position})')
                lines.append(f'    elem_{k}.color = {tuple(elem.color)}')

    elif node.bl_idname == 'ShaderNodeTexNoise':
        lines.append(
            f'    {var_name}.noise_dimensions = \'{node.noise_dimensions}\'')
        if hasattr(node, 'noise_type'):
            lines.append(f'    {var_name}.noise_type = \'{node.noise_type}\'')
        if hasattr(node, 'normalize'):
            lines.append(f'    {var_name}.normalize = {node.normalize}')

    elif node.bl_idname == 'ShaderNodeTexVoronoi':
        lines.append(
            f'    {var_name}.voronoi_dimensions = \'{node.voronoi_dimensions}\'')
        lines.append(f'    {var_name}.feature = \'{node.feature}\'')
        lines.append(f'    {var_name}.distance = \'{node.distance}\'')
        if hasattr(node, 'normalize'):
            lines.append(f'    {var_name}.normalize = {node.normalize}')

    elif node.bl_idname == 'ShaderNodeTexGradient':
        lines.append(
            f'    {var_name}.gradient_type = \'{node.gradient_type}\'')

    elif node.bl_idname == 'ShaderNodeTexWave':
        lines.append(f'    {var_name}.wave_type = \'{node.wave_type}\'')
        lines.append(
            f'    {var_name}.bands_direction = \'{node.bands_direction}\'')
        lines.append(f'    {var_name}.wave_profile = \'{node.wave_profile}\'')

    elif node.bl_idname == 'ShaderNodeTexMusgrave':
        lines.append(
            f'    {var_name}.musgrave_dimensions = \'{node.musgrave_dimensions}\'')
        lines.append(
            f'    {var_name}.musgrave_type = \'{node.musgrave_type}\'')

    elif node.bl_idname == 'ShaderNodeTexImage':
        if node.image:
            lines.append(
                f'    # Note: Image "{node.image.name}" needs to be loaded separately')
            lines.append(
                f'    # {var_name}.image = bpy.data.images.load("path/to/image")')
        lines.append(
            f'    {var_name}.interpolation = \'{node.interpolation}\'')
        lines.append(f'    {var_name}.projection = \'{node.projection}\'')
        lines.append(f'    {var_name}.extension = \'{node.extension}\'')

    elif node.bl_idname == 'ShaderNodeBsdfPrincipled':
        lines.append(f'    {var_name}.distribution = \'{node.distribution}\'')
        lines.append(
            f'    {var_name}.subsurface_method = \'{node.subsurface_method}\'')

    elif node.bl_idname == 'ShaderNodeBump':
        lines.append(f'    {var_name}.invert = {node.invert}')

    elif node.bl_idname == 'ShaderNodeNormalMap':
        lines.append(f'    {var_name}.space = \'{node.space}\'')

    elif node.bl_idname == 'ShaderNodeSeparateColor':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'ShaderNodeCombineColor':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'ShaderNodeClamp':
        lines.append(f'    {var_name}.clamp_type = \'{node.clamp_type}\'')

    elif node.bl_idname == 'ShaderNodeVectorRotate':
        lines.append(
            f'    {var_name}.rotation_type = \'{node.rotation_type}\'')
        lines.append(f'    {var_name}.invert = {node.invert}')

    elif node.bl_idname == 'GeometryNodeGroup':
        if node.node_tree:
            lines.append(f'    # Nested node group: {node.node_tree.name}')
            lines.append(
                f'    if "{node.node_tree.name}" in bpy.data.node_groups:')
            lines.append(
                f'        {var_name}.node_tree = bpy.data.node_groups["{node.node_tree.name}"]')
            lines.append(f'    else:')
            lines.append(
                f'        print("Warning: Node group \\"{node.node_tree.name}\\" not found. Please create it first.")')

    elif node.bl_idname == 'ShaderNodeGroup':
        if node.node_tree:
            lines.append(f'    # Nested node group: {node.node_tree.name}')
            lines.append(
                f'    if "{node.node_tree.name}" in bpy.data.node_groups:')
            lines.append(
                f'        {var_name}.node_tree = bpy.data.node_groups["{node.node_tree.name}"]')
            lines.append(f'    else:')
            lines.append(
                f'        print("Warning: Node group \\"{node.node_tree.name}\\" not found. Please create it first.")')

    elif node.bl_idname == 'FunctionNodeCompare':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')
        lines.append(f'    {var_name}.operation = \'{node.operation}\'')
        if hasattr(node, 'mode'):
            lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'GeometryNodeSwitch':
        lines.append(f'    {var_name}.input_type = \'{node.input_type}\'')

    elif node.bl_idname == 'FunctionNodeBooleanMath':
        lines.append(f'    {var_name}.operation = \'{node.operation}\'')

    elif node.bl_idname == 'GeometryNodeObjectInfo':
        lines.append(
            f'    {var_name}.transform_space = \'{node.transform_space}\'')

    elif node.bl_idname == 'GeometryNodeCollectionInfo':
        lines.append(
            f'    {var_name}.transform_space = \'{node.transform_space}\'')

    elif node.bl_idname == 'GeometryNodeRaycast':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')

    elif node.bl_idname == 'GeometryNodeAttributeStatistic':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')
        lines.append(f'    {var_name}.domain = \'{node.domain}\'')

    elif node.bl_idname == 'GeometryNodeCaptureAttribute':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')
        lines.append(f'    {var_name}.domain = \'{node.domain}\'')

    elif node.bl_idname == 'GeometryNodeStoreNamedAttribute':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')
        lines.append(f'    {var_name}.domain = \'{node.domain}\'')

    elif node.bl_idname == 'GeometryNodeInputNamedAttribute':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')

    elif node.bl_idname == 'GeometryNodeSampleIndex':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')
        lines.append(f'    {var_name}.domain = \'{node.domain}\'')
        lines.append(f'    {var_name}.clamp = {node.clamp}')

    elif node.bl_idname == 'GeometryNodeSampleNearest':
        lines.append(f'    {var_name}.domain = \'{node.domain}\'')

    elif node.bl_idname == 'GeometryNodeProximity':
        lines.append(
            f'    {var_name}.target_element = \'{node.target_element}\'')

    elif node.bl_idname == 'GeometryNodeMeshBoolean':
        lines.append(f'    {var_name}.operation = \'{node.operation}\'')

    elif node.bl_idname == 'GeometryNodeSubdivisionSurface':
        lines.append(f'    {var_name}.uv_smooth = \'{node.uv_smooth}\'')
        lines.append(
            f'    {var_name}.boundary_smooth = \'{node.boundary_smooth}\'')

    elif node.bl_idname == 'GeometryNodeExtrudeMesh':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'GeometryNodeDeleteGeometry':
        lines.append(f'    {var_name}.domain = \'{node.domain}\'')
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'GeometryNodeSeparateGeometry':
        lines.append(f'    {var_name}.domain = \'{node.domain}\'')

    elif node.bl_idname == 'GeometryNodeMergeByDistance':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'GeometryNodeMeshToPoints':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'GeometryNodeDistributePointsOnFaces':
        lines.append(
            f'    {var_name}.distribute_method = \'{node.distribute_method}\'')
        if hasattr(node, 'use_legacy_normal'):
            lines.append(
                f'    {var_name}.use_legacy_normal = {node.use_legacy_normal}')

    elif node.bl_idname == 'GeometryNodeCurvePrimitiveCircle':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'GeometryNodeCurvePrimitiveLine':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'GeometryNodeCurvePrimitiveQuadrilateral':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'GeometryNodeFillCurve':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'GeometryNodeResampleCurve':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'GeometryNodeTrimCurve':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'GeometryNodeSetCurveHandlePositions':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')

    elif node.bl_idname == 'GeometryNodeCurveHandleTypeSelection':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')
        lines.append(f'    {var_name}.handle_type = \'{node.handle_type}\'')

    elif node.bl_idname == 'GeometryNodeSetCurveHandleType':
        lines.append(f'    {var_name}.mode = \'{node.mode}\'')
        lines.append(f'    {var_name}.handle_type = \'{node.handle_type}\'')

    elif node.bl_idname == 'GeometryNodeSetSplineType':
        lines.append(f'    {var_name}.spline_type = \'{node.spline_type}\'')

    elif node.bl_idname == 'GeometryNodeViewer':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')
        if hasattr(node, 'domain'):
            lines.append(f'    {var_name}.domain = \'{node.domain}\'')

    elif node.bl_idname == 'GeometryNodeAccumulateField':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')
        lines.append(f'    {var_name}.domain = \'{node.domain}\'')

    elif node.bl_idname == 'GeometryNodeFieldAtIndex':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')
        lines.append(f'    {var_name}.domain = \'{node.domain}\'')

    elif node.bl_idname == 'FunctionNodeRandomValue':
        lines.append(f'    {var_name}.data_type = \'{node.data_type}\'')

    elif node.bl_idname == 'GeometryNodeTriangulate':
        if hasattr(node, 'quad_method'):
            lines.append(
                f'    {var_name}.quad_method = \'{node.quad_method}\'')
        if hasattr(node, 'ngon_method'):
            lines.append(
                f'    {var_name}.ngon_method = \'{node.ngon_method}\'')

    elif node.bl_idname == 'GeometryNodeTransform':
        pass  # No special properties beyond inputs

    elif node.bl_idname == 'GeometryNodeSetPosition':
        pass  # No special properties beyond inputs

    elif node.bl_idname == 'GeometryNodeMeshGrid':
        pass  # No special properties beyond inputs

    elif node.bl_idname == 'GeometryNodeRealizeInstances':
        pass  # No special properties beyond inputs

    # Generic fallback
    else:
        try:
            for prop in node.bl_rna.properties:
                if prop.identifier in SKIP_PROPS:
                    continue
                if prop.is_readonly:
                    continue

                if prop.type == 'ENUM':
                    try:
                        value = getattr(node, prop.identifier)
                        if value is not None:
                            lines.append(
                                f'    {var_name}.{prop.identifier} = \'{value}\'')
                    except:
                        pass
                elif prop.type == 'BOOLEAN':
                    try:
                        value = getattr(node, prop.identifier)
                        if value is not None:
                            lines.append(
                                f'    {var_name}.{prop.identifier} = {value}')
                    except:
                        pass
        except:
            pass


class NODE_OT_export_to_python(bpy.types.Operator):
    """Export the active node group to Python code"""
    bl_idname = "node.export_to_python"
    bl_label = "Export Node Group to Python"
    bl_options = {'REGISTER', 'UNDO'}

    copy_to_clipboard: BoolProperty(
        name="Copy to Clipboard",
        default=True,
        description="Copy the generated code to clipboard"
    )

    save_to_file: BoolProperty(
        name="Save to File",
        default=False,
        description="Save the generated code to a file"
    )

    auto_assign: BoolProperty(
        name="Auto-assign to Context",
        default=True,
        description="Automatically assign node group (Geometry Nodes to object, Shaders to material)"
    )

    include_nested: BoolProperty(
        name="Include Nested Node Groups",
        default=True,
        description="Export nested node groups as dependencies (recommended for complete exports)"
    )

    filepath: StringProperty(
        name="Directory Path",
        default="",
        subtype='DIR_PATH',
        description="Directory where the file will be saved (filename will be auto-generated)"
    )

    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'NODE_EDITOR' and
                context.space_data.edit_tree is not None)

    def execute(self, context):
        node_tree = context.space_data.edit_tree

        if node_tree is None:
            self.report({'ERROR'}, "No node tree found")
            return {'CANCELLED'}

        # Check if user is trying to export a material-level shader tree
        if hasattr(node_tree, 'nodes'):
            # Check if this is a material's node tree (has Material Output but no interface)
            has_material_output = any(
                node.type == 'OUTPUT_MATERIAL' for node in node_tree.nodes)
            has_interface = hasattr(node_tree, 'interface') and len(
                list(node_tree.interface.items_tree)) > 0

            if has_material_output and not has_interface:
                self.report({'WARNING'},
                            "You're exporting a material tree. To export only a node group, Tab into it first!")

        python_code = export_node_group_to_python(
            node_tree, auto_assign=self.auto_assign, include_nested=self.include_nested)

        if self.copy_to_clipboard:
            context.window_manager.clipboard = python_code
            self.report(
                {'INFO'}, f"Python code copied to clipboard ({len(python_code)} characters)")

        if self.save_to_file and self.filepath:
            try:
                # Auto-generate filename based on node group name
                filename = f"{sanitize_name(node_tree.name)}.py"

                # Check if filepath is a directory or full path
                if os.path.isdir(self.filepath):
                    # It's a directory, combine with auto-generated filename
                    full_path = os.path.join(self.filepath, filename)
                else:
                    # Check if the parent directory exists (might be a full path)
                    parent_dir = os.path.dirname(self.filepath)
                    if parent_dir and os.path.isdir(parent_dir):
                        # Use the provided path as-is (backwards compatibility)
                        full_path = self.filepath
                    else:
                        # Treat as directory path and create if needed
                        os.makedirs(self.filepath, exist_ok=True)
                        full_path = os.path.join(self.filepath, filename)

                with open(full_path, 'w') as f:
                    f.write(python_code)
                self.report({'INFO'}, f"Saved to {full_path}")
            except Exception as e:
                self.report({'ERROR'}, f"Failed to save file: {str(e)}")
                return {'CANCELLED'}

        text_name = f"{node_tree.name}_export.py"
        if text_name in bpy.data.texts:
            text_block = bpy.data.texts[text_name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(text_name)

        text_block.write(python_code)
        self.report({'INFO'}, f"Code also saved to text block: {text_name}")

        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "copy_to_clipboard")
        layout.prop(self, "auto_assign")
        layout.prop(self, "include_nested")
        layout.prop(self, "save_to_file")
        if self.save_to_file:
            layout.prop(self, "filepath")
            # Show the auto-generated filename
            node_tree = context.space_data.edit_tree
            if node_tree:
                filename = f"{sanitize_name(node_tree.name)}.py"
                box = layout.box()
                box.label(text=f"Filename: {filename}", icon='FILE_SCRIPT')


class NODE_OT_export_to_python_quick(bpy.types.Operator):
    """Quick export - copies to clipboard immediately"""
    bl_idname = "node.export_to_python_quick"
    bl_label = "Quick Export to Clipboard"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'NODE_EDITOR' and
                context.space_data.edit_tree is not None)

    def execute(self, context):
        node_tree = context.space_data.edit_tree

        if node_tree is None:
            self.report({'ERROR'}, "No node tree found")
            return {'CANCELLED'}

        # Check if user is trying to export a material-level shader tree
        if hasattr(node_tree, 'nodes'):
            has_material_output = any(
                node.type == 'OUTPUT_MATERIAL' for node in node_tree.nodes)
            has_interface = hasattr(node_tree, 'interface') and len(
                list(node_tree.interface.items_tree)) > 0

            if has_material_output and not has_interface:
                self.report({'WARNING'},
                            "Exporting material tree. To export only a node group, Tab into it first!")

        python_code = export_node_group_to_python(
            node_tree, auto_assign=True, include_nested=True)
        context.window_manager.clipboard = python_code

        text_name = f"{node_tree.name}_export.py"
        if text_name in bpy.data.texts:
            text_block = bpy.data.texts[text_name]
            text_block.clear()
        else:
            text_block = bpy.data.texts.new(text_name)
        text_block.write(python_code)

        self.report(
            {'INFO'}, f"Exported '{node_tree.name}' to clipboard and text block")
        return {'FINISHED'}


class NODE_PT_export_panel(bpy.types.Panel):
    """Panel in the Node Editor sidebar for exporting node groups"""
    bl_label = "Node Group Export"
    bl_idname = "NODE_PT_export_panel"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Export'

    def draw(self, context):
        layout = self.layout

        node_tree = context.space_data.edit_tree

        if node_tree:
            layout.label(text=f"Current: {node_tree.name}")
            layout.label(text=f"Type: {node_tree.bl_idname}")
            layout.label(text=f"Nodes: {len(node_tree.nodes)}")
            layout.label(text=f"Links: {len(node_tree.links)}")

            # Show nested groups info
            nested_groups = find_nested_node_groups(node_tree)
            if nested_groups:
                layout.label(
                    text=f"Nested Groups: {len(nested_groups)}", icon='NODETREE')

            layout.separator()

            row = layout.row(align=True)
            row.scale_y = 2.0
            row.operator("node.export_to_python_quick",
                         text="Export to Clipboard", icon='COPYDOWN')

            layout.separator()

            layout.operator("node.export_to_python",
                            text="Export with Options...", icon='EXPORT')

            layout.separator()

            box = layout.box()
            box.label(text="Output locations:", icon='INFO')
            box.label(text="• Clipboard (paste anywhere)")
            box.label(text="• Text Editor block")

            if node_tree.bl_idname == 'GeometryNodeTree':
                layout.separator()
                box2 = layout.box()
                box2.label(text="Geometry Nodes:", icon='GEOMETRY_NODES')
                box2.label(text="Auto-creates object and")
                box2.label(text="assigns the node group")
            elif node_tree.bl_idname == 'ShaderNodeTree':
                layout.separator()
                box2 = layout.box()
                box2.label(text="Shader Nodes:", icon='SHADING_SOLID')
                box2.label(text="Adds as single group node")
                box2.label(text="(not expanded)")

            # Show warning if exporting material-level tree
            if node_tree.bl_idname == 'ShaderNodeTree' and hasattr(node_tree, 'nodes'):
                has_material_output = any(
                    node.type == 'OUTPUT_MATERIAL' for node in node_tree.nodes)
                has_interface = hasattr(node_tree, 'interface') and len(
                    list(node_tree.interface.items_tree)) > 0

                if has_material_output and not has_interface:
                    layout.separator()
                    warn_box = layout.box()
                    warn_box.alert = True
                    warn_box.label(text="⚠ Material Level", icon='ERROR')
                    warn_box.label(text="To export a node group:")
                    warn_box.label(text="1. Select the group node")
                    warn_box.label(text="2. Press TAB to enter it")
                    warn_box.label(text="3. Then export")

            # Show tip for node group export
            layout.separator()
            tip_box = layout.box()
            tip_box.label(text="Quick Guide:", icon='INFO')
            if node_tree.bl_idname in ('ShaderNodeTree', 'GeometryNodeTree'):
                tip_box.label(text="• Export at material level:")
                tip_box.label(text="  → Full material/object setup")
                tip_box.label(text="• Export inside node group:")
                tip_box.label(text="  → Just that group")
        else:
            layout.label(text="No node tree active")
            layout.label(text="Enter a node group to export")


def draw_header_button(self, context):
    if context.space_data.type == 'NODE_EDITOR' and context.space_data.edit_tree:
        self.layout.operator("node.export_to_python_quick",
                             text="", icon='EXPORT')


classes = (
    NODE_OT_export_to_python,
    NODE_OT_export_to_python_quick,
    NODE_PT_export_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.NODE_HT_header.append(draw_header_button)


def unregister():
    bpy.types.NODE_HT_header.remove(draw_header_button)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
