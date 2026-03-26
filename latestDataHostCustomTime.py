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


def get_time_range():
    """Hàm cho phép chọn khoảng thời gian giống trên Web"""
    print("\n--- SELECT TIME RANGE ---")
    print("1. Last 1 hour")
    print("2. Last 1 day")
    print("3. Last 7 days")
    print("4. Last 30 days (Default)")
    choice = input("Select an option (1-4) or press Enter for default: ").strip()

    mapping = {
        "1": 3600,  # 1h
        "2": 86400,  # 1d
        "3": 86400 * 7,  # 7d
        "4": 86400 * 30  # 30d
    }
    seconds = mapping.get(choice, 86400 * 30)
    return int(time.time()) - seconds, seconds // 3600


def get_zabbix_interactive_report():
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

        tag_values = {}
        for item in items:
            for t in item.get('tags', []):
                if t['tag'] == 'component':
                    val = t['value']
                    tag_values[val] = tag_values.get(val, 0) + 1

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
                print(f"No items found for group '{keyword}'.")
                continue

            # Bước mới: Hỏi thời gian
            time_from, hours_limit = get_time_range()

            table = PrettyTable()
            table.field_names = ["ITEM NAME", "MIN", "AVG", "MAX", "LAST"]
            table.align["ITEM NAME"] = "l"
            for col in ["MIN", "AVG", "MAX", "LAST"]: table.align[col] = "r"

            for item in matched_items:
                unit = item['units']
                last_raw = item['lastvalue']

                if item['value_type'] in ['0', '3']:
                    # Lấy dữ liệu Trends
                    trends = zapi.trend.get(itemids=item['itemid'], time_from=time_from,
                                            output=['value_min', 'value_avg', 'value_max'])

                    if trends:
                        min_v = min([float(t['value_min']) for t in trends])
                        max_v = max([float(t['value_max']) for t in trends])
                        avg_v = statistics.mean([float(t['value_avg']) for t in trends])
                    else:
                        # Nếu thời gian quá ngắn (như 1h), có thể chưa có Trends, thử lấy từ History
                        history = zapi.history.get(itemids=item['itemid'], history=item['value_type'],
                                                   time_from=time_from, limit=100)
                        if history:
                            h_vals = [float(h['value']) for h in history]
                            min_v, max_v, avg_v = min(h_vals), max(h_vals), statistics.mean(h_vals)
                        else:
                            val = float(last_raw) if last_raw else 0
                            min_v = avg_v = max_v = val

                    table.add_row(
                        [item['name'], format_value(min_v, unit), format_value(avg_v, unit), format_value(max_v, unit),
                         format_value(last_raw, unit)])
                else:
                    table.add_row([item['name'], "-", "-", "-", last_raw if last_raw else "No data"])

            print(f"\n--- Statistics for '{keyword}' (Last {hours_limit} hours) ---")
            print(table)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    get_zabbix_interactive_report()