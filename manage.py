from pyzabbix import ZabbixAPI
import urllib3
import datetime
import time
import statistics
from prettytable import PrettyTable

# --- CẤU HÌNH CHUNG ---
ZABBIX_URL = 'http://192.168.46.128:8080/api_jsonrpc.php'
API_TOKEN = '545acb8c8a4513f8587684a9bc6618b1184b928c5a18be92e844561b9b72dbd1'

# Vô hiệu hóa cảnh báo SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ZabbixManager:
    def __init__(self):
        self.zapi = ZabbixAPI(ZABBIX_URL)
        try:
            self.zapi.login(api_token=API_TOKEN)
            print(f"Connected to Zabbix API: {ZABBIX_URL}")
        except Exception as e:
            print(f"Connection Error: {e}")
            exit()

    # --- UTILS (Hàm bổ trợ) ---
    def format_duration(self, seconds):
        d, h, m, s = seconds // 86400, (seconds % 86400) // 3600, (seconds % 3600) // 60, seconds % 60
        parts = []
        if d > 0: parts.append(f"{int(d)}d")
        if h > 0: parts.append(f"{int(h)}h")
        if m > 0: parts.append(f"{int(m)}m")
        if s > 0 or not parts: parts.append(f"{int(s)}s")
        return " ".join(parts)

    def format_value(self, value, unit):
        if value is None: return "-"
        try:
            val_float = float(value)
        except:
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

    # --- CHỨC NĂNG 1: LIST ALL HOSTS ---
    def list_all_hosts(self):
        print("\n" + "=" * 80)
        print(f"{'--- ZABBIX HOST LIST ---':^80}")
        hosts = self.zapi.host.get(
            output=['hostid', 'host', 'name', 'status'],
            selectInterfaces=['ip', 'dns', 'useip', 'port', 'available'],
            sortfield='name'
        )

        table = PrettyTable()
        table.field_names = ["NAME", "INTERFACE", "AVAILABILITY", "STATUS"]
        table.align = "l"

        for h in hosts:
            interfaces = h.get('interfaces', [])
            if interfaces:
                main_if = interfaces[0]
                if_str = f"{main_if['ip'] if main_if['useip'] == '1' else main_if['dns']}:{main_if['port']}"
                avail_map = {'0': 'Unknown', '1': 'ZBX', '2': 'Unavailable'}
                avail_str = avail_map.get(str(main_if.get('available', '0')), 'Unknown')
            else:
                if_str, avail_str = "None", "Unknown"

            status_str = "Enabled" if h['status'] == '0' else "Disabled"
            table.add_row([h['name'], if_str, avail_str, status_str])

        print(table)

    # --- CHỨC NĂNG 2: PROBLEM REPORT ---
    def problem_report(self):
        print("\n--- SELECT TIME RANGE FOR PROBLEMS ---")
        print("1. 1h  2. 24h  3. 7d  4. 30d  5. 6m  6. 1y")
        choice = input("Choice (1-6) [Default 30d]: ").strip()
        now = int(time.time())
        mapping = {"1": 3600, "2": 86400, "3": 86400 * 7, "4": 86400 * 30, "5": 86400 * 180, "6": 86400 * 365}
        time_from = now - mapping.get(choice, 86400 * 30)

        raw_problems = self.zapi.problem.get(
            output=['eventid', 'name', 'severity', 'clock', 'r_clock', 'objectid'],
            time_from=time_from, sortfield='eventid', sortorder='DESC'
        )

        if not raw_problems:
            return print("No problems found.")

        # Get Hostnames
        trigger_ids = list(set([p['objectid'] for p in raw_problems]))
        triggers = self.zapi.trigger.get(triggerids=trigger_ids, selectHosts=['name'], output=['triggerid'])
        host_map = {t['triggerid']: t['hosts'][0]['name'] for t in triggers if t.get('hosts')}

        table = PrettyTable()
        table.field_names = ["START TIME", "HOST", "DURATION", "SEVERITY", "PROBLEM"]
        table.align["PROBLEM"] = "l"

        severity_map = {'0': 'NC', '1': 'Info', '2': 'Warning', '3': 'Average', '4': 'High', '5': 'Disaster'}

        for p in raw_problems:
            start_str = datetime.datetime.fromtimestamp(int(p['clock'])).strftime('%Y-%m-%d %H:%M')
            duration = self.format_duration((int(p.get('r_clock', 0)) or now) - int(p['clock']))
            table.add_row(
                [start_str, host_map.get(p['objectid'], "N/A"), duration, severity_map.get(p['severity'], 'N/A'),
                 p['name'][:50]])

        print(table)

    # --- CHỨC NĂNG 3: LATEST DATA & STATS ---
    def latest_data_stats(self):
        host_name = input("Enter Host Name to check: ").strip()
        hosts = self.zapi.host.get(filter={"name": host_name}, output=["hostid"])
        if not hosts: return print("Host not found!")

        items = self.zapi.item.get(hostids=hosts[0]['hostid'],
                                   output=["itemid", "name", "units", "value_type", "lastvalue"],
                                   selectTags=["tag", "value"])

        tags = sorted(list(set(t['value'] for i in items for t in i.get('tags', []) if t['tag'] == 'component')))
        print("\nAvailable Components:", ", ".join(tags))
        keyword = input("Enter component tag (e.g. CPU, Memory): ").lower().strip()

        matched = [i for i in items if
                   any(t['value'].lower() == keyword for t in i.get('tags', []) if t['tag'] == 'component')]
        if not matched: return print("No items found.")

        print("Select Time: 1. 1h  2. 1d  3. 7d  4. 30d")
        t_choice = input("Choice: ").strip()
        t_map = {"1": 3600, "2": 86400, "3": 86400 * 7, "4": 86400 * 30}
        time_from = int(time.time()) - t_map.get(t_choice, 86400 * 30)

        table = PrettyTable(["ITEM NAME", "MIN", "AVG", "MAX", "LAST"])
        table.align["ITEM NAME"] = "l"

        for item in matched:
            min_v, avg_v, max_v = "-", "-", "-"
            if item['value_type'] in ['0', '3']:
                trends = self.zapi.trend.get(itemids=item['itemid'], time_from=time_from,
                                             output=['value_min', 'value_avg', 'value_max'])
                if trends:
                    min_v = self.format_value(min([float(t['value_min']) for t in trends]), item['units'])
                    max_v = self.format_value(max([float(t['value_max']) for t in trends]), item['units'])
                    avg_v = self.format_value(statistics.mean([float(t['value_avg']) for t in trends]), item['units'])

            table.add_row([item['name'], min_v, avg_v, max_v, self.format_value(item['lastvalue'], item['units'])])

        print(table)


# --- MAIN MENU ---
def main():
    manager = ZabbixManager()
    while True:
        print("\n" + "╔" + "═" * 38 + "╗")
        print("║       ZABBIX MANAGEMENT SYSTEM       ║")
        print("╠" + "═" * 38 + "╣")
        print("║ 1. List All Hosts                    ║")
        print("║ 2. View Problem History              ║")
        print("║ 3. View Host Latest Data & Stats     ║")
        print("║ 4. Exit                              ║")
        print("╚" + "═" * 38 + "╝")

        choice = input("Select an option (1-4): ").strip()

        if choice == '1':
            manager.list_all_hosts()
        elif choice == '2':
            manager.problem_report()
        elif choice == '3':
            manager.latest_data_stats()
        elif choice == '4':
            print("Exiting... Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()