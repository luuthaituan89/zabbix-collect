from pyzabbix import ZabbixAPI
import time
import urllib3
import statistics
from prettytable import PrettyTable

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ZABBIX_URL = 'http://192.168.46.128:8080/api_jsonrpc.php'
API_TOKEN = '545acb8c8a4513f8587684a9bc6618b1184b928c5a18be92e844561b9b72dbd1'


def format_value(value, unit):
    """Hàm format chuẩn: 1000 cho bps, 1024 cho Bytes"""
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

    res = ("%.4f" % val_float).rstrip('0').rstrip('.')
    return f"{res if res else '0'} {unit}".strip()


def get_zabbix_interactive_report():
    zapi = ZabbixAPI(ZABBIX_URL)
    try:
        zapi.login(api_token=API_TOKEN)

        # Nhập Host một lần duy nhất ở đầu
        host_name = input("Enter Host Name: ").strip()
        hosts = zapi.host.get(filter={"name": host_name}, output=["hostid", "name"])
        if not hosts: return print("Host not found!")
        host_id = hosts[0]['hostid']

        # Lấy items và tags một lần để tối ưu tốc độ
        items = zapi.item.get(
            hostids=host_id,
            output=["itemid", "name", "units", "value_type", "lastvalue"],
            selectTags=["tag", "value"]
        )

        # Tính toán danh sách Tag Values (Subfilters)
        tag_values = {}
        for item in items:
            for t in item.get('tags', []):
                if t['tag'] == 'component':
                    val = t['value']
                    tag_values[val] = tag_values.get(val, 0) + 1

        # VÒNG LẶP TƯƠNG TÁC
        while True:
            print("\n" + "=" * 50)
            print("TAG VALUES (Available groups):")
            for val, count in sorted(tag_values.items()):
                print(f"- {val} ({count})")

            print("-" * 50)
            keyword = input("Enter tag value to view (or type 'exit' to quit): ").lower().strip()

            if keyword == 'exit':
                print("Exiting program. Goodbye!")
                break

            matched_items = [i for i in items if
                             any(t['value'].lower() == keyword for t in i.get('tags', []) if t['tag'] == 'component')]

            if not matched_items:
                print(f"No items found for group '{keyword}'. Please try again.")
                continue

            table = PrettyTable()
            table.field_names = ["ITEM NAME", "MIN", "AVG", "MAX", "LAST"]
            table.align["ITEM NAME"] = "l"
            for col in ["MIN", "AVG", "MAX", "LAST"]: table.align[col] = "r"

            time_from = int(time.time()) - (30 * 24 * 60 * 60)

            for item in matched_items:
                unit = item['units']
                last_raw = item['lastvalue']

                if item['value_type'] in ['0', '3']:
                    trends = zapi.trend.get(itemids=item['itemid'], time_from=time_from,
                                            output=['value_min', 'value_avg', 'value_max'])

                    if trends:
                        min_v = min([float(t['value_min']) for t in trends])
                        max_v = max([float(t['value_max']) for t in trends])
                        avg_v = statistics.mean([float(t['value_avg']) for t in trends])
                    else:
                        try:
                            val = float(last_raw) if last_raw else 0
                            min_v = avg_v = max_v = val
                        except:
                            min_v = avg_v = max_v = None

                    table.add_row(
                        [item['name'], format_value(min_v, unit), format_value(avg_v, unit), format_value(max_v, unit),
                         format_value(last_raw, unit)])
                else:
                    # Xử lý dữ liệu văn bản (như OS info)
                    table.add_row([item['name'], "-", "-", "-", last_raw if last_raw else "No data"])

            print(f"\n--- Statistics for group '{keyword}' (Last 30 Days) ---")
            print(table)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    get_zabbix_interactive_report()