import pandas as pd
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

# Load the Excel file
file_path = 'intersection_traffic.xlsx'

# Define the route mapping for each direction
route_mappings = {
    'eastbound': {
        'left': 'Eb_l',
        'right': 'Eb_r',
        'center': 'Eb_s'
    },
    'westbound': {
        'left': 'Wb_l',
        'right': 'Wb_r',
        'center': 'Wb_s'
    },
    'southbound': {
        'left': 'Sb_l',
        'right': 'Sb_r',
        'center': 'Sb_s'
    },
    'northbound': {
        'left': 'Nb_l',
        'right': 'Nb_r',
        'center': 'Nb_s'
    }
}

# Load the existing routes from the XML file
tree = ET.parse('test.rou.xml')
root = tree.getroot()

# Define vehicle types based on SUMO's abstract vehicle classes
vehicle_types = {
    'car': {"id": "car", "vClass": "passenger"},
    'hov': {"id": "hov", "vClass": "passenger"},
    'bus': {"id": "bus", "vClass": "bus"},
    'delivery': {"id": "delivery", "vClass": "delivery"},
    'truck': {"id": "truck", "vClass": "truck"},
    'trailer': {"id": "trailer", "vClass": "trailer"}
}

# Add vehicle type definitions to the XML
for vehicle_type in vehicle_types.values():
    ET.SubElement(
        root,
        'vType',
        id=vehicle_type["id"],
        vClass=vehicle_type["vClass"]
    )


# Function to add flows from a specific sheet
def add_flows_from_sheet(sheet_name, route_mapping):
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=0, usecols="A:T", nrows=26)
    morning_df = df.iloc[:12]  # Assuming each row represents 15 minutes

    flow_id = len(root.findall('flow'))  # Ensure unique flow IDs across all sheets
    time_interval = 15 * 60  # 15 minutes in seconds

    for index, row in morning_df.iterrows():
        start_time = index * time_interval
        end_time = start_time + time_interval
        for route in ['left', 'right', 'center']:
            for vehicle_type in vehicle_types:
                flow_key = f'{route}-{vehicle_type}'
                if flow_key in row:
                    flow_value = int(row[flow_key])
                    if flow_value > 0:
                        ET.SubElement(
                            root,
                            'flow',
                            id=f'f_{flow_id}',
                            begin=str(start_time),
                            end=str(end_time),
                            route=route_mapping[route],
                            number=str(flow_value),
                            type=vehicle_type
                        )
                        flow_id += 1


# Process each sheet
for direction, route_mapping in route_mappings.items():
    add_flows_from_sheet(direction, route_mapping)


# Pretty-print the XML
def pretty_print_xml(element):
    """Return a pretty-printed XML string for the Element."""
    rough_string = ET.tostring(element, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


# Get the pretty-printed XML string
pretty_xml_as_string = pretty_print_xml(root)

# Write the pretty-printed XML to a file
output_file_path = 'generated_flows.xml'
with open(output_file_path, 'w', encoding='utf-8') as f:
    f.write(pretty_xml_as_string)

print(f'Successfully generated the SUMO flows XML file and saved as {output_file_path}.')
