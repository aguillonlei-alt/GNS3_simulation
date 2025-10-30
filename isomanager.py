import paramiko
import time
import os
from datetime import datetime, timedelta
import hashlib

# ------------------------------
# CONFIGURATION SECTION
# ------------------------------
DEVICES = {
    "PE": {"ip": "192.168.122.147", "username": "admin", "password": "cisco"},
    "EOR1": {"ip": "10.0.0.2", "username": "admin", "password": "cisco"},
    "SPINE": {"ip": "10.0.1.2", "username": "admin", "password": "cisco"},
}

BACKUP_DIR = "./backups"
LOG_FILE = "./backup_log.txt"
DAYS_TO_KEEP = 7

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

def cleanup_old_backups():
    """Delete backups older than DAYS_TO_KEEP."""
    now = datetime.now()
    for f in os.listdir(BACKUP_DIR):
        file_path = os.path.join(BACKUP_DIR, f)
        if os.path.isfile(file_path):
            mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            if (now - mtime).days > DAYS_TO_KEEP:
                os.remove(file_path)
                log(f"[🧹] Deleted old backup: {f}")

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

def get_running_config(client):
    """Run 'show running-config' and return output."""
    shell = client.invoke_shell()
    time.sleep(1)
    shell.send("terminal length 0\n")
    time.sleep(1)
    shell.send("show running-config\n")
    time.sleep(5)
    output = shell.recv(99999).decode(errors="ignore")
    return output

def save_backup(device_name, output):
    """Save config and detect changes."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    filename = f"{BACKUP_DIR}/{device_name}_running-config_{timestamp}.txt"

    # Save new backup
    with open(filename, "w") as f:
        f.write(output)

    # Compare with previous backup (if any)
    previous_files = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith(device_name)],
        reverse=True
    )
    if len(previous_files) > 1:
        with open(os.path.join(BACKUP_DIR, previous_files[1]), "r") as prev_file:
            old_config = prev_file.read()
            if md5sum(old_config) != md5sum(output):
                log(f"[⚠️] {device_name} configuration CHANGED since last backup!")
            else:
                log(f"[✅] {device_name} configuration unchanged.")
    else:
        log(f"[+] First backup for {device_name} created.")

    log(f"[💾] Saved backup for {device_name}: {filename}")

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

    # Get PE config
    shell.send("terminal length 0\n")
    time.sleep(1)
    shell.send("show running-config\n")
    time.sleep(5)
    output_pe = shell.recv(99999).decode(errors="ignore")
    save_backup("PE", output_pe)

    # Step 2: From PE → EOR1
    log("[↪] Hopping into EOR1...")
    shell.send("ssh -l admin 10.0.0.2\n")
    time.sleep(2)
    shell.send("cisco\n")
    time.sleep(3)
    shell.send("terminal length 0\nshow running-config\n")
    time.sleep(6)
    output_eor1 = shell.recv(99999).decode(errors="ignore")
    save_backup("EOR1", output_eor1)

    # Step 3: From EOR1 → SPINE
    log("[↪] Hopping into SPINE from EOR1...")
    shell.send("ssh -l admin 10.0.1.2\n")
    time.sleep(2)
    shell.send("cisco\n")
    time.sleep(3)
    shell.send("terminal length 0\nshow running-config\n")
    time.sleep(6)
    output_spine = shell.recv(99999).decode(errors="ignore")
    save_backup("SPINE", output_spine)

    shell.close()
    pe.close()

    cleanup_old_backups()
    log("[✅] Backup process complete for PE, EOR1, and SPINE.")
    log("-" * 50)

# ------------------------------
# RUN SCRIPT
# ------------------------------
if __name__ == "__main__":
    backup_all()
