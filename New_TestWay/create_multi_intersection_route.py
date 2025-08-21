import pandas as pd
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import re

# ———————————————————————
# 1) 파일 경로 설정
# ———————————————————————
excel_path = 'multi_intersection_traffic.xlsx'
route_path = 'single_multi_route_v2.rou.xml'
output_path = 'generated_single_multi_flows_v2.xml'

# ———————————————————————
# 2) 교차로 ID 맵핑
# ———————————————————————
intersection_id_map = {
    '한국건설기술연구원 앞 삼거리': '1',
    '고양체육관사거리':           '2',
    '고양종합운동장사거리':       '3'
}

# ———————————————————————
# 3) 차량 유형 정의
# ———————————————————————
vehicle_types = {
    'car':      {"id": "car",      "vClass": "passenger"},
    'hov':      {"id": "hov",      "vClass": "hov"},
    'bus':      {"id": "bus",      "vClass": "bus"},
    'delivery': {"id": "delivery", "vClass": "delivery"},
    'truck':    {"id": "truck",    "vClass": "truck"},
    'trailer':  {"id": "trailer",  "vClass": "trailer"}
}

# ———————————————————————
# 4) 기본 Route 이름 및 departLane 매핑
# ———————————————————————
base_route_mappings = {
    'EastBound':  {'left': 'EB_l', 'right': 'EB_r', 'center': 'EB_s', 'uturn': 'EB_u'},
    'WestBound':  {'left': 'WB_l', 'right': 'WB_r', 'center': 'WB_s', 'uturn': 'WB_u'},
    'SouthBound': {'left': 'SB_l', 'right': 'SB_r', 'center': 'SB_s', 'uturn': 'SB_u'},
    'NorthBound': {'left': 'NB_l', 'right': 'NB_r', 'center': 'NB_s', 'uturn': 'NB_u'},
}

depart_lane_mappings = {
    'EastBound':  {'left': '2', 'right': '0', 'center': '1', 'uturn': '2'},
    'WestBound':  {'left': '2', 'right': '0', 'center': '1', 'uturn': '2'},
    'SouthBound': {'left': '2', 'right': '0', 'center': '1', 'uturn': '2'},
    'NorthBound': {'left': '2', 'right': '0', 'center': '1', 'uturn': '2'},
}

# ———————————————————————
# 5) DataFrame 인덱스 기준 direction별 블록 범위
#    (header=2 사용 시, df.index=0 → Excel row 4)
# ———————————————————————
direction_rows = {
    'EastBound':  ( 0, 11),   # Excel 행 4~15 → df 0~11
    'WestBound':  (15, 26),   # Excel 행 19~30 → df 15~26
    'SouthBound': (30, 41),   # Excel 행 34~45 → df 30~41
    'NorthBound': (45, 56),   # Excel 행 49~60 → df 45~56
}

# ———————————————————————
# 6) 기존 route XML 로드 및 vType 추가
# ———————————————————————
tree = ET.parse(route_path)
root = tree.getroot()

for vt in vehicle_types.values():
    ET.SubElement(root,
                  'vType',
                  id=vt['id'],
                  vClass=vt['vClass'])

# ———————————————————————
# 7) Flow 생성 루프
# ———————————————————————
flows = []
flow_id = 0

xls = pd.ExcelFile(excel_path)
valid_sheets = [s for s in xls.sheet_names if s in intersection_id_map]

for sheet in valid_sheets:
    # — header=2 → 세 번째 행(0-based idx=2)을 컬럼명으로 사용
    df = pd.read_excel(excel_path, sheet_name=sheet, header=2)

    # 두 번째 컬럼(시간) 자동으로 'Unnamed: 1'으로 읽히므로 'Time'으로 변경
    time_col = df.columns[1]
    df.rename(columns={time_col: 'Time'}, inplace=True)

    intersection_id = intersection_id_map[sheet]
    # 교차로 ID를 붙인 route 이름 생성
    route_mappings = {
        dir_key: {
            turn: f"{intersection_id}_{base_route_mappings[dir_key][turn]}"
            for turn in base_route_mappings[dir_key]
        }
        for dir_key in base_route_mappings
    }

    base_time_sec = None

    for direction, (start_idx, end_idx) in direction_rows.items():
        block = df.iloc[start_idx:end_idx+1].reset_index(drop=True)
        # block.columns[2:] 은 'left-car', 'left-hov', ...
        for col in block.columns[2:]:
            if '-' not in col:
                continue
            turn, vtype = col.split('-', 1)
            if turn not in route_mappings[direction]:
                continue
            if vtype not in vehicle_types:
                continue

            for i, ts in enumerate(block['Time']):
                ts_str = str(ts)
                if '~' not in ts_str:
                    continue
                m = re.match(r'(\d{2}):(\d{2})', ts_str.split('~')[0].strip())
                if not m:
                    continue
                hour, minute = int(m.group(1)), int(m.group(2))
                curr_sec = hour * 3600 + minute * 60

                if base_time_sec is None:
                    base_time_sec = curr_sec
                begin = curr_sec - base_time_sec
                end_t = begin + 300  # 5분 간격

                try:
                    cnt = int(block.at[i, col])
                except:
                    continue
                if cnt <= 0:
                    continue

                flows.append({
                    'id':         f'f_{flow_id}',
                    'begin':      begin,
                    'end':        end_t,
                    'departLane': depart_lane_mappings[direction][turn],
                    'route':      route_mappings[direction][turn],
                    'number':     cnt,
                    'type':       vtype
                })
                flow_id += 1

# ———————————————————————
# 8) Flow 정렬 후 XML에 추가
# ———————————————————————
flows.sort(key=lambda x: (x['begin'], x['end'], x['route'], x['id']))

for f in flows:
    ET.SubElement(root,
                  'flow',
                  id=f['id'],
                  begin=str(f['begin']),
                  end=str(f['end']),
                  departLane=str(f['departLane']),
                  route=f['route'],
                  number=str(f['number']),
                  type=f['type'])

# ———————————————————————
# 9) XML 저장
# ———————————————————————
with open(output_path, 'w', encoding='utf-8') as fout:
    pretty = minidom.parseString(ET.tostring(root, encoding='utf-8')) \
                    .toprettyxml(indent="  ")
    fout.write(pretty)

print(f"SUMO flow XML 파일 생성 완료: {output_path}")
