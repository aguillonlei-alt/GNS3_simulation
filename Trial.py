import csv
import paramiko
import time
import schedule

def get_cisco_config(hostname, username, password, enable_password):
    try:
        # Connect to the Cisco device using SSH
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname, username=username, password=password)

        # Create a shell session
        shell = ssh_client.invoke_shell()

        # Send enable command
        shell.send("enable\n")
        time.sleep(1)
        shell.send(enable_password + "\n")

        # Send command to retrieve running configuration
        shell.send("terminal length 0\n")  # Prevent pagination
        shell.send("show running-config\n")

        # Wait for the command to execute
        time.sleep(5)

        # Read the output of the command
        output = ""
        while shell.recv_ready():
            output += shell.recv(1024).decode()

        # Close SSH connection
        ssh_client.close()
        return output

    except Exception as e:
        print(f"Error retrieving configuration from {hostname}: {e}")
        return None


def upload_to_sftp(server, username, password, local_path, remote_path):
    try:
        # Establish an SFTP connection to the server
        transport = paramiko.Transport((server, 22))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        print("SFTP connection OK")

        # Upload the file
        sftp.put(local_path, remote_path)

        # Close SFTP connection
        sftp.close()
        print(f"Configuration uploaded to {server} at {remote_path}")

    except Exception as e:
        print(f"Error uploading configuration to {server}: {e}")


def main():
    # Read router information from CSV file
    routers = []
    with open('router_credentials.csv', 'r') as csvfile:
        csv_reader = csv.reader(csvfile)
        next(csv_reader)  # Skip the header row
        for row in csv_reader:
            routers.append({
                "hostname": row[0],
                "username": row[1],
                "password": row[2],
                "enable_password": row[3]
            })

    # SFTP server credentials
    sftp_server = "192.168.37.128"  # IP address of the SFTP server
    sftp_username = "gns3"           # Username for accessing the SFTP server
    sftp_password = "gns3"           # Password for accessing the SFTP server

    for router in routers:
        config = get_cisco_config(
            router["hostname"],
            router["username"],
            router["password"],
            router["enable_password"]
        )

        if config:
            # Save running configuration to a local file
            local_path = f"running_config_{router['hostname']}.txt"
            with open(local_path, "w") as f:
                f.write(config)
            print("File ready")

            # Upload the running configuration to SFTP server
            upload_to_sftp(
                sftp_server,
                sftp_username,
                sftp_password,
                local_path,
                f"/home/gns3/remote_backups/running_config_{router['hostname']}.txt"
            )


# Schedule the main function to run every minute
schedule.every(1).minutes.do(main)

# Infinite loop to keep the script running
while True:
    schedule.run_pending()
    time.sleep(1)  # Wait 1 second before checking the schedule again
