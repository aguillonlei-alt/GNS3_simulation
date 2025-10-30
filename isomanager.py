import paramiko
import time
import os
from datetime import datetime

# --- SSH / Device Info ---
PE_IP = "192.168.122.147"
USERNAME = "admin"
PASSWORD = "cisco"
BACKUP_DIR = "./backups"
IOS_IMAGE = "new_ios.bin"  # The IOS file stored in your GNS3 VM (SCP server)
VM_SCP_SERVER = "192.168.122.1"  # or your GNS3 host IP if using NAT cloud

# --- Helper Functions ---

def send_cmd(shell, cmd, delay=2):
    shell.send(cmd + "\n")
    time.sleep(delay)
    output = shell.recv(99999).decode(errors="ignore")
    return output

def backup_device(shell, hostname):
    """Backup running-config and save to timestamped file"""
    send_cmd(shell, "enable")
    send_cmd(shell, PASSWORD)
    send_cmd(shell, "terminal length 0")
    output = send_cmd(shell, "show running-config", delay=4)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    filename = f"{BACKUP_DIR}/{hostname}_running-config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, "w") as f:
        f.write(output)
    print(f"[💾] Saved backup for {hostname}: {filename}")

def apply_ios_patch(shell, hostname):
    """Simulate IOS patch update (copy, verify, set bootvar, reload)"""
    print(f"[⚙️] Applying IOS patch to {hostname}...")

    # Copy new IOS image from VM to router flash
    send_cmd(shell, f"copy scp://{USERNAME}@{VM_SCP_SERVER}/{IOS_IMAGE} flash:")
    send_cmd(shell, PASSWORD, delay=1)

    # Verify image
    send_cmd(shell, f"verify /md5 flash:{IOS_IMAGE}", delay=5)

    # Set boot variable
    send_cmd(shell, f"conf t")
    send_cmd(shell, f"boot system flash:{IOS_IMAGE}")
    send_cmd(shell, f"end")

    # Save config
    send_cmd(shell, "write memory", delay=3)
    print(f"[✅] IOS patch applied successfully to {hostname} (pending reload)")

def connect_to_pe():
    """Establish SSH connection to PE"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(PE_IP, username=USERNAME, password=PASSWORD,
                   look_for_keys=False, allow_agent=False)
    shell = client.invoke_shell()
    time.sleep(1)
    print(f"[+] Connected to PE ({PE_IP})")
    return client, shell

# --- Main Process ---

def main():
    print("[🚀] Starting automated backup + IOS patch sequence...\n")

    client, shell = connect_to_pe()

    # === PE ===
    print("[*] Backing up and patching PE...")
    backup_device(shell, "PE")
    apply_ios_patch(shell, "PE")

    # === EOR1 ===
    print("\n[*] Hopping into EOR1 (via PE)...")
    send_cmd(shell, "ssh -l admin 10.0.0.2")
    send_cmd(shell, PASSWORD, delay=2)
    backup_device(shell, "EOR1")
    apply_ios_patch(shell, "EOR1")

    # === SPINE ===
    print("\n[*] Hopping into SPINE (via EOR1)...")
    send_cmd(shell, "ssh -l admin 10.0.1.2")
    send_cmd(shell, PASSWORD, delay=2)
    backup_device(shell, "SPINE")
    apply_ios_patch(shell, "SPINE")

    print("\n✅ All routers (PE, EOR1, SPINE) backed up and patched successfully!")
    client.close()

if __name__ == "__main__":
    main()
