import pandas as pd
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

# 엑셀 파일 로드
file_path = 'intersection_traffic.xlsx'

# 각 방향에 대한 경로 매핑 정의
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

# 기존 경로 XML 파일 로드
tree = ET.parse('test.rou.xml')
root = tree.getroot()

# SUMO의 추상 차량 클래스를 기반으로 차량 유형 정의
vehicle_types = {
    'car': {"id": "car", "vClass": "passenger"},
    'hov': {"id": "hov", "vClass": "passenger"},
    'bus': {"id": "bus", "vClass": "bus"},
    'delivery': {"id": "delivery", "vClass": "delivery"},
    'truck': {"id": "truck", "vClass": "truck"},
    'trailer': {"id": "trailer", "vClass": "trailer"}
}

# 차량 유형 정의를 XML에 추가
for vehicle_type in vehicle_types.values():
    ET.SubElement(
        root,
        'vType',
        id=vehicle_type["id"],
        vClass=vehicle_type["vClass"]
    )

flows = []


# 특정 시트에서 흐름을 추가하는 함수
def add_flows_from_sheet(sheet_name, route_mapping, flow_id):
    df = pd.read_excel(file_path, sheet_name=sheet_name, header=0, usecols="A:T", nrows=26)
    morning_df = df.iloc[:12]  # 각 행이 15분을 나타낸다고 가정

    time_interval = 15 * 60  # 15분을 초로 변환

    for index, row in morning_df.iterrows():
        start_time = index * time_interval
        end_time = start_time + time_interval
        for route in ['left', 'right', 'center']:
            for vehicle_type in vehicle_types:
                flow_key = f'{route}-{vehicle_type}'
                if flow_key in row:
                    flow_value = int(row[flow_key])
                    if flow_value > 0:
                        flows.append({
                            'id': f'f_{flow_id}',
                            'begin': start_time,
                            'end': end_time,
                            'route': route_mapping[route],
                            'number': flow_value,
                            'type': vehicle_type
                        })
                        flow_id += 1
    return flow_id


# 흐름 ID 카운터 초기화
flow_id = 0

# 각 시트를 처리하고 방향별로 흐름을 그룹화
for direction, route_mapping in route_mappings.items():
    flow_id = add_flows_from_sheet(direction, route_mapping, flow_id)

# 흐름을 정렬합니다.
flows.sort(key=lambda x: (x['begin'], x['end'], x['route'], x['id']))

# 정렬된 흐름을 XML에 추가합니다.
for flow in flows:
    ET.SubElement(
        root,
        'flow',
        id=flow['id'],
        begin=str(flow['begin']),
        end=str(flow['end']),
        route=flow['route'],
        number=str(flow['number']),
        type=flow['type']
    )


# XML을 예쁘게 출력하는 함수
def pretty_print_xml(element):
    """요소에 대한 예쁘게 출력된 XML 문자열 반환."""
    rough_string = ET.tostring(element, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


# 예쁘게 출력된 XML 문자열 가져오기
pretty_xml_as_string = pretty_print_xml(root)

# 예쁘게 출력된 XML을 파일에 쓰기
output_file_path = 'generated_flows.xml'
with open(output_file_path, 'w', encoding='utf-8') as f:
    f.write(pretty_xml_as_string)

print(f'Successfully generated the SUMO flows XML file and saved as {output_file_path}.')
