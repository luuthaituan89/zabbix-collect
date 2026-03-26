from pyzabbix import ZabbixAPI
import datetime
import time
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Configuration
ZABBIX_URL = 'http://192.168.46.128:8080/api_jsonrpc.php'
API_TOKEN = '545acb8c8a4513f8587684a9bc6618b1184b928c5a18be92e844561b9b72dbd1'


def format_duration(seconds):
    """Convert seconds into a human-readable duration string."""
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


def get_zabbix_history_30days():
    zapi = ZabbixAPI(ZABBIX_URL)

    try:
        zapi.login(api_token=API_TOKEN)

        current_time = int(time.time())
        thirty_days_ago = current_time - (30 * 24 * 60 * 60)

        # 2. Query Problem History
        problems = zapi.problem.get(
            output=['eventid', 'name', 'severity', 'clock', 'r_clock'],
            recent=False,
            time_from=thirty_days_ago,
            sortfield='eventid',
            sortorder='DESC'
        )

        print("--- LIST OF PROBLEMS IN THE LAST 30 DAYS ---")

        if not problems:
            print("No problems found in the specified period.")
            return

        # 3. Print Header with DURATION
        header = f"{'START TIME':<20} | {'RECOVERY TIME':<20} | {'DURATION':<15} | {'SEVERITY':<12} | {'PROBLEM NAME'}"
        print(header)
        print("-" * 130)

        severity_map = {
            '0': 'Not classified', '1': 'Information', '2': 'Warning',
            '3': 'Average', '4': 'High', '5': 'Disaster'
        }

        for p in problems:
            start_ts = int(p['clock'])
            recovery_ts = int(p.get('r_clock', 0))

            # Format Start Time
            start_time_str = datetime.datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d %H:%M:%S')

            # Logic for Recovery Time and Duration calculation
            if recovery_ts != 0:
                recovery_time_str = datetime.datetime.fromtimestamp(recovery_ts).strftime('%Y-%m-%d %H:%M:%S')
                duration_seconds = recovery_ts - start_ts
            else:
                recovery_time_str = ""
                duration_seconds = current_time - start_ts  # Ongoing duration

            duration_str = format_duration(duration_seconds)
            sev_name = severity_map.get(p['severity'], 'Unknown')

            # Print row
            print(f"{start_time_str:<20} | {recovery_time_str:<20} | {duration_str:<15} | {sev_name:<12} | {p['name']}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    get_zabbix_history_30days()