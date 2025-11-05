import paramiko
import time
import os
from datetime import datetime
import hashlib
import schedule

# ------------------------------
# CONFIGURATION SECTION
# ------------------------------
DEVICES = {
    "PE": {"ip": "192.168.122.147", "username": "admin", "password": "cisco"},
    "EOR1": {"ip": "10.0.0.2", "username": "admin", "password": "cisco"},
    "SPINE": {"ip": "10.0.1.2", "username": "admin", "password": "cisco"},
}

# Save directly to your current folder (~/backups/backups)
BACKUP_DIR = "."
LOG_FILE = "./backup_log.txt"

CISCO_SSH_CONFIG = {
    'kex_algorithms': ['diffie-hellman-group1-sha1', 'diffie-hellman-group14-sha1'],
    'encryption_algorithms': ['aes128-ctr', 'aes128-cbc', '3des-cbc'],
    'mac_algorithms': ['hmac-sha1', 'hmac-sha1-96']
}

# ------------------------------
# UTILITY FUNCTIONS
# ------------------------------
def log(msg):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(LOG_FILE, "a") as log_file:
        log_file.write(f"{timestamp} {msg}\n")
    print(msg)

def md5sum(text):
    """Generate MD5 hash of a config for comparison."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def ssh_connect(host, username, password):
    """Connect to a Cisco router."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    paramiko.transport.Transport._preferred_kex = CISCO_SSH_CONFIG['kex_algorithms']
    paramiko.transport.Transport._preferred_ciphers = CISCO_SSH_CONFIG['encryption_algorithms']
    paramiko.transport.Transport._preferred_macs = CISCO_SSH_CONFIG['mac_algorithms']

    client.connect(hostname=host, username=username, password=password,
                   look_for_keys=False, allow_agent=False, timeout=10)
    return client

def get_running_config(shell):
    """Run 'show running-config' and return full output."""
    shell.send("terminal length 0\n")
    time.sleep(1)
    shell.send("show running-config\n")
    time.sleep(8)  # wait to ensure full config output
    output = ""
    while shell.recv_ready():
        output += shell.recv(99999).decode(errors="ignore")
        time.sleep(1)
    return output

def save_backup(device_name, output):
    """Save config with timestamped filename."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{BACKUP_DIR}/{device_name}_running-config_.txt"
    with open(filename, "w") as f:
        f.write(output)
    log(f"[💾] Saved backup for {device_name}: {filename}")
    log(f"[DEBUG] {device_name} config size: {len(output)} characters")

# ------------------------------
# MAIN BACKUP FLOW
# ------------------------------
def backup_all():
    log("[🚀] Starting automated multi-hop backup sequence...")

    # Step 1: Connect to PE
    pe = ssh_connect(DEVICES["PE"]["ip"], DEVICES["PE"]["username"], DEVICES["PE"]["password"])
    log("[+] Connected to PE.")
    shell = pe.invoke_shell()
    time.sleep(1)

    # Backup PE
    output_pe = get_running_config(shell)
    save_backup("PE", output_pe)

    # Step 2: From PE → EOR1
    log("[↪] Hopping into EOR1...")
    shell.send("ssh -l admin 10.0.0.2\n")
    time.sleep(2)
    shell.send("cisco\n")
    time.sleep(3)
    output_eor1 = get_running_config(shell)
    save_backup("EOR1", output_eor1)

    # Step 3: From EOR1 → SPINE
    log("[↪] Hopping into SPINE from EOR1...")
    shell.send("ssh -l admin 10.0.1.2\n")
    time.sleep(2)
    shell.send("cisco\n")
    time.sleep(3)
    output_spine = get_running_config(shell)
    save_backup("SPINE", output_spine)

    shell.close()
    pe.close()

    log("[✅] Backup process complete for PE, EOR1, and SPINE.")
    log("-" * 60)

# ------------------------------
# SCHEDULER
# ------------------------------
schedule.every(1).minutes.do(backup_all)

# Infinite loop to keep the script running
while True:
    schedule.run_pending()
    time.sleep(1)
