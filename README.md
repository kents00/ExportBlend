# ExportBlend

Export your Blender node groups to readable, executable Python code with one click.

![ezgif-19899e4bfce2737b](https://github.com/user-attachments/assets/7b21d02b-ddcf-4d79-9879-0a2fdb99cfa9)

## Introduction

ExportBlend is a Blender addon that converts your node groups (Geometry Nodes and Shader Nodes) into clean, well-structured Python code. Whether you're building procedural generators, creating shader libraries, or sharing your node setups, ExportBlend makes it easy to turn visual node graphs into portable, reusable Python scripts.

## Problem

Working with Blender's node systems presents several challenges:

- **Sharing Node Setups**: Sending `.blend` files is cumbersome and version-dependent
- **Version Control**: Binary `.blend` files don't work well with Git and other VCS
- **Procedural Generation**: No easy way to programmatically create complex node setups
- **Documentation**: Difficult to document node configurations in a readable format
- **Automation**: Hard to batch-create similar node setups across multiple files
- **Learning**: Understanding node relationships is easier when viewing code structure
- **Backup**: Exporting node logic separately from blend files provides additional safety

## Solution

ExportBlend solves these problems by:

1. **Converting node graphs to Python code** - Transform visual nodes into readable, executable scripts
2. **Automatic dependency handling** - Recursively exports nested node groups in the correct order
3. **Smart context assignment** - Auto-generates code to assign Geometry Nodes to objects and Shaders to materials
4. **Multiple export options** - Copy to clipboard, save to file, or export to text editor
5. **Preserving all properties** - Captures node settings, connections, socket values, and interface definitions
6. **Clean, idiomatic code** - Generated Python follows best practices and is easy to understand

## Features

### Core Functionality
- **One-Click Export** - Quick export button in the Node Editor header
- **Clipboard Integration** - Instantly copy generated code for pasting anywhere
- **File Export** - Save with auto-generated filenames based on node group names
- **Text Editor Integration** - Automatically creates text blocks in Blender

### Node Support
- **Geometry Nodes** - Full support for Blender 4.0+ Geometry Node trees
- **Shader Nodes** - Complete shader node group export
- **Nested Node Groups** - Automatically detects and exports dependencies
- **All Node Properties** - Preserves settings, values, and configurations

### Smart Features
- **Auto-Assignment**
  - Geometry Nodes: Creates objects and assigns modifiers
  - Shader Nodes: Creates materials and adds node groups
- **Nested Group Detection** - Shows count of nested dependencies
- **Smart Warnings** - Alerts when exporting material-level vs node group-level
- **Interface Export** - Captures input/output sockets for Blender 4.0+

### Export Options
- **Toggle Nested Groups** - Choose to include or exclude dependencies
- **Auto-Assign Context** - Enable/disable automatic object/material assignment
- **Directory Selection** - Choose save location with auto-generated filenames
- **Export Preview** - See nested group counts and node tree information

## Installation

1. Download the `__init__.py` file
2. Open Blender
3. Go to `Edit` → `Preferences` → `Add-ons`
4. Click `Install...` and select the downloaded file
5. Enable "Node: ExportBlend"

## Usage

### Quick Export (Recommended)
1. Open the Node Editor
2. Tab into the node group you want to export
3. Click the export icon in the header or use the sidebar panel
4. Code is copied to clipboard and saved to text editor

### Export with Options
1. Open Node Editor sidebar (N key)
2. Navigate to the "Export" tab
3. Configure options:
   - **Copy to Clipboard** - Copy code for pasting elsewhere
   - **Auto-assign to Context** - Include assignment code
   - **Include Nested Node Groups** - Export dependencies
   - **Save to File** - Export to a Python file
4. Click "Export with Options..."

### Important: Exporting Node Groups vs Materials

**To export ONLY a node group:**
1. Select the node group node in your material/object
2. Press **TAB** to enter the node group
3. Export from inside the group

**Exporting at material/object level** will export the entire setup including Material Output, which creates different code.

## Generated Code Example

```python
import bpy

def create_my_shader_node_group():
    """Create the My Shader node group."""

    # Check if node group already exists
    if "My Shader" in bpy.data.node_groups:
        return bpy.data.node_groups["My Shader"]

    # Create new node group
    node_group = bpy.data.node_groups.new(name="My Shader", type='ShaderNodeTree')

    # Create nodes
    # ... (node creation code)

    # Create links
    # ... (connection code)

    return node_group

# Create the node group
node_group = create_my_shader_node_group()
print(f"Node group \"{node_group.name}\" created successfully!")
```

## Requirements

- Blender 4.0 or higher
- Python 3.10+ (bundled with Blender)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

GNU GENERAL PUBLIC LICENSE

## Author

Kent Edoloverio

## Support

For issues, questions, or suggestions, please open an issue on the GitHub repository.
