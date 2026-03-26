from pyzabbix import ZabbixAPI
import time
import urllib3
import statistics
from prettytable import PrettyTable

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ZABBIX_URL = 'http://192.168.46.128:8080/api_jsonrpc.php'
API_TOKEN = '545acb8c8a4513f8587684a9bc6618b1184b928c5a18be92e844561b9b72dbd1'


def draw_bar(value, max_val=100):
    """Vẽ biểu đồ thanh bằng ký tự ASCII"""
    if value is None or not isinstance(value, (int, float)) or max_val <= 0:
        return ""
    bar_length = 15  # Độ dài tối đa của thanh biểu đồ
    scaled_val = min(int((value / max_val) * bar_length), bar_length)
    return "█" * scaled_val + "░" * (bar_length - scaled_val)


def format_value(value, unit):
    """Hàm format đơn vị chuẩn"""
    if value is None: return "-"
    try:
        val_float = float(value)
    except (ValueError, TypeError):
        return str(value)

    if unit.lower() == "bps":
        for u in ['bps', 'Kbps', 'Mbps', 'Gbps']:
            if val_float < 1000: return f"{val_float:.2f} {u}".rstrip('0').rstrip('.')
            val_float /= 1000
    elif unit == "B":
        for u in ['B', 'KB', 'MB', 'GB', 'TB']:
            if val_float < 1024: return f"{val_float:.2f} {u}".rstrip('0').rstrip('.')
            val_float /= 1024

    res = ("%.2f" % val_float).rstrip('0').rstrip('.')
    return f"{res if res else '0'} {unit}".strip()


def get_zabbix_visual_report():
    zapi = ZabbixAPI(ZABBIX_URL)
    try:
        zapi.login(api_token=API_TOKEN)
        host_name = input("Enter Host Name: ").strip()
        hosts = zapi.host.get(filter={"name": host_name}, output=["hostid", "name"])
        if not hosts: return print("Host not found!")
        host_id = hosts[0]['hostid']

        items = zapi.item.get(
            hostids=host_id,
            output=["itemid", "name", "units", "value_type", "lastvalue"],
            selectTags=["tag", "value"]
        )

        tag_dict = {}
        for item in items:
            for t in item.get('tags', []):
                if t['tag'] == 'component':
                    tag_dict[t['value']] = tag_dict.get(t['value'], 0) + 1

        while True:
            print("\n" + "=" * 60)
            print("AVAILABLE GROUPS (TAG: component):")
            for val, count in sorted(tag_dict.items()):
                print(f"- {val} ({count})")

            keyword = input("\nEnter group to view (or 'exit'): ").lower().strip()
            if keyword == 'exit': break

            # Chọn thời gian
            print("\n1. 1h | 2. 1d | 3. 7d | 4. 30d")
            t_choice = input("Select time (1-4, default 4): ")
            days = {"1": 1 / 24, "2": 1, "3": 7, "4": 30}.get(t_choice, 30)
            time_from = int(time.time()) - int(days * 86400)

            matched = [i for i in items if
                       any(t['value'].lower() == keyword for t in i.get('tags', []) if t['tag'] == 'component')]

            table = PrettyTable()
            table.field_names = ["ITEM NAME", "AVG", "LAST", "VISUAL (LAST)"]
            table.align["ITEM NAME"], table.align["VISUAL (LAST)"] = "l", "l"

            for item in matched:
                unit = item['units']
                last_raw = item['lastvalue']

                if item['value_type'] in ['0', '3']:
                    trends = zapi.trend.get(itemids=item['itemid'], time_from=time_from, output=['value_avg'])
                    avg_v = statistics.mean([float(t['value_avg']) for t in trends]) if trends else (
                        float(last_raw) if last_raw else 0)

                    # Giả định max_val để vẽ biểu đồ (100 cho %, hoặc tự scale cho Memory)
                    max_scale = 100 if unit == "%" else (
                        float(last_raw) * 1.2 if last_raw and float(last_raw) > 0 else 100)

                    table.add_row([
                        item['name'],
                        format_value(avg_v, unit),
                        format_value(last_raw, unit),
                        draw_bar(float(last_raw) if last_raw else 0, max_scale)
                    ])
                else:
                    table.add_row([item['name'], "-", last_raw, "N/A"])

            print(f"\n--- Visual Report for '{keyword}' ---")
            print(table)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    get_zabbix_visual_report()