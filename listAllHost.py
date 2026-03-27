from pyzabbix import ZabbixAPI
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Configuration
ZABBIX_URL = 'http://192.168.46.128:8080/api_jsonrpc.php'
API_TOKEN = '545acb8c8a4513f8587684a9bc6618b1184b928c5a18be92e844561b9b72dbd1'


def get_zabbix_hosts_clean():
    zapi = ZabbixAPI(ZABBIX_URL)

    try:
        # Authenticate using Token
        zapi.login(api_token=API_TOKEN)

        # 2. Query Hosts (Removed selectTags to be lightweight)
        hosts = zapi.host.get(
            output=['hostid', 'host', 'name', 'status'],
            selectInterfaces=['ip', 'dns', 'useip', 'port', 'available'],
            sortfield='name'
        )

        print(f"--- ZABBIX HOST LIST (Total: {len(hosts)}) ---\n")

        # 3. Print Header (Removed Tags column)
        header = f"{'NAME':<25} | {'INTERFACE':<25} | {'AVAILABILITY':<12} | {'STATUS':<10}"
        print(header)
        print("-" * len(header))

        for h in hosts:
            # --- Interface & Availability ---
            interfaces = h.get('interfaces', [])
            interface_str = "None"
            availability_str = "Unknown"

            if interfaces:
                main_if = interfaces[0]
                # Check if using IP or DNS
                if main_if['useip'] == '1':
                    interface_str = f"{main_if['ip']}:{main_if['port']}"
                else:
                    interface_str = f"{main_if['dns']}:{main_if['port']}"

                # Availability Map (0: Unknown, 1: Available/ZBX, 2: Unavailable)
                avail_map = {'0': 'Unknown', '1': 'ZBX', '2': 'Unavailable'}
                availability_str = avail_map.get(str(main_if.get('available', '0')), 'Unknown')

            # --- Status (0: Enabled, 1: Disabled) ---
            status_str = "Enabled" if h['status'] == '0' else "Disabled"

            # Print formatted row
            print(f"{h['name']:<25} | {interface_str:<25} | {availability_str:<12} | {status_str:<10}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    get_zabbix_hosts_clean()