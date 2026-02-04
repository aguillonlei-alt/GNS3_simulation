import csv
import re
import threading
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# For reference only, edit according to the routers configuration
USER_PASS_COMBOS = [
    ('admin', 'Cisco123'),
    ('manager', 'Welcome1'),
    # Add your list here...
]

PASS_ONLY_COMBOS = [
    'cisco',
    'password',
    # Add your list here...
]

ENABLE_SECRET = 'secret123'
MAX_THREADS = 50  # Keep this at 50 to avoid network congestion
OUTPUT_FILE = 'router_report_4000.csv'

# Create a lock so threads don't write to the file at the exact same time
csv_lock = threading.Lock()

def get_router_details(ip):
    result = {
        'IP': ip,
        'Model': 'Unknown',
        'IOS_Version': 'Unknown',
        'Serial': 'Unknown',
        'Status': 'Failed (Auth/Timeout)',
        'Creds_Used': 'None'
    }

    successful_conn = None

    # --- PHASE 1: Try Username/Password Combos ---
    for user, pwd in USER_PASS_COMBOS:
        try:
            conn = ConnectHandler(
                device_type='cisco_ios',
                host=ip,
                username=user,
                password=pwd,
                secret=ENABLE_SECRET,
                fast_cli=False
            )
            successful_conn = conn
            result['Creds_Used'] = f"User: {user}"
            break
        except (NetmikoAuthenticationException, Exception):
            continue 
        except NetmikoTimeoutException:
            result['Status'] = "Device Unreachable (Timeout)"
            return result 

    # --- PHASE 2: Try Password Only Combos ---
    if not successful_conn:
        for pwd in PASS_ONLY_COMBOS:
            try:
                conn = ConnectHandler(
                    device_type='cisco_ios',
                    host=ip,
                    username='',
                    password=pwd,
                    secret=ENABLE_SECRET,
                    fast_cli=False
                )
                successful_conn = conn
                result['Creds_Used'] = "Pass Only"
                break 
            except (NetmikoAuthenticationException, Exception):
                continue
            except NetmikoTimeoutException:
                result['Status'] = "Device Unreachable (Timeout)"
                return result

    # --- PHASE 3: Run Commands ---
    if successful_conn:
        try:
            output = successful_conn.send_command("show version")
            successful_conn.disconnect()

            version_match = re.search(r"Version\s+([^,]+)", output)
            if version_match: result['IOS_Version'] = version_match.group(1)

            model_match = re.search(r"[Cc]isco\s+(\S+).+bytes of memory", output)
            if not model_match:
                model_match = re.search(r"[Cc]isco\s+(\S+)\s+\(.+\)\s+processor", output)
            if model_match: result['Model'] = model_match.group(1)
            
            serial_match = re.search(r"Processor board ID (\S+)", output)
            if serial_match: result['Serial'] = serial_match.group(1)

            result['Status'] = 'Success'
            print(f"✅ Success: {ip}")

        except Exception as e:
            result['Status'] = f"Parse Error: {str(e)[:30]}"
            print(f"⚠️  Parse Error: {ip}")
    else:
        print(f"⛔ Auth Failed: {ip}")

    return result

def main():
    start_time = datetime.now()
    
    # Load IPs
    try:
        with open('routers.txt', 'r') as f:
            ip_list = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: 'routers.txt' not found.")
        return

    print(f"--- Starting Scan on {len(ip_list)} Routers ---")
    
    # Initialize the CSV file with headers
    headers = ['IP', 'Model', 'IOS_Version', 'Serial', 'Status', 'Creds_Used']
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

    # Process routers and save IMMEDIATELY upon completion
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # 'future_to_ip' maps the running task to the IP address
        future_to_ip = {executor.submit(get_router_details, ip): ip for ip in ip_list}
        
        for future in as_completed(future_to_ip):
            data = future.result()
            
            # Write this single result to CSV immediately
            with csv_lock:
                with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writerow(data)

    print(f"\nCompleted in {datetime.now() - start_time}")

if __name__ == "__main__":
    main()
