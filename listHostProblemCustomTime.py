from pyzabbix import ZabbixAPI
import datetime
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ZABBIX_URL = 'http://192.168.46.128:8080/api_jsonrpc.php'
API_TOKEN = '545acb8c8a4513f8587684a9bc6618b1184b928c5a18be92e844561b9b72dbd1'


def format_duration(seconds):
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    parts = []
    if d > 0: parts.append(f"{int(d)}d")
    if h > 0: parts.append(f"{int(h)}h")
    if m > 0: parts.append(f"{int(m)}m")
    if s > 0 or not parts: parts.append(f"{int(s)}s")
    return " ".join(parts)


def select_time_range():
    print("\n" + "=" * 45)
    print("      SELECT TIME RANGE")
    print("1. Last 1 hour      2. Last 24 hours")
    print("3. Last 7 days      4. Last 30 days")
    print("5. Last 6 months    6. Last 1 year")
    print("=" * 45)
    choice = input("Enter choice (1-6) or Enter for default: ").strip()
    now = int(time.time())
    mapping = {
        "1": (now - 3600, "1 hour"),
        "2": (now - 86400, "24 hours"),
        "3": (now - 86400 * 7, "7 days"),
        "4": (now - 86400 * 30, "30 days"),
        "5": (now - 86400 * 180, "6 months"),
        "6": (now - 86400 * 365, "1 year")
    }
    return mapping.get(choice, (now - 86400 * 30, "30 days"))


def get_zabbix_problem_report():
    zapi = ZabbixAPI(ZABBIX_URL)
    try:
        zapi.login(api_token=API_TOKEN)

        while True:
            time_from, label = select_time_range()
            current_time = int(time.time())

            # 1. Lấy danh sách Problems (chỉ lấy các trường cần thiết)
            raw_problems = zapi.problem.get(
                output=['eventid', 'name', 'severity', 'clock', 'r_clock', 'objectid'],
                selectAcknowledges='extend',
                sortfield='eventid',
                sortorder='DESC'
            )

            # Lọc theo thời gian
            problems = [p for p in raw_problems if int(p['clock']) >= time_from]

            print(f"\n--- LIST OF PROBLEMS IN THE {label.upper()} ---")

            if not problems:
                print(f"No problems found starting within the last {label}.")
            else:
                # 2. TỐI ƯU: Lấy danh sách trigger IDs để truy vấn Host Name 1 lần duy nhất
                trigger_ids = list(set([p['objectid'] for p in problems]))
                triggers = zapi.trigger.get(
                    triggerids=trigger_ids,
                    selectHosts=['name'],
                    output=['triggerid']
                )

                # Tạo bản đồ: {trigger_id: host_name}
                host_map = {}
                for t in triggers:
                    if t.get('hosts'):
                        host_map[t['triggerid']] = t['hosts'][0]['name']

                # 3. Hiển thị bảng dữ liệu
                header = f"{'START TIME':<20} | {'HOST':<20} | {'DURATION':<12} | {'SEVERITY':<12} | {'PROBLEM'}"
                print(header)
                print("-" * 150)

                severity_map = {
                    '0': 'Not classified', '1': 'Information', '2': 'Warning',
                    '3': 'Average', '4': 'High', '5': 'Disaster'
                }

                for p in problems:
                    host_name = host_map.get(p['objectid'], "Unknown")
                    start_ts = int(p['clock'])
                    recovery_ts = int(p.get('r_clock', 0))
                    start_str = datetime.datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d %H:%M:%S')

                    duration_sec = (recovery_ts if recovery_ts != 0 else current_time) - start_ts
                    duration_str = format_duration(duration_sec)
                    sev_name = severity_map.get(p['severity'], 'Unknown')

                    print(f"{start_str:<20} | {host_name:<20} | {duration_str:<12} | {sev_name:<12} | {p['name']}")

            print("-" * 150)
            cont = input("Check another time range? (y/n): ").lower().strip()
            if cont != 'y':
                print("Exiting. Goodbye!")
                break

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    get_zabbix_problem_report()