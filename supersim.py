from dotenv import dotenv_values
import subprocess, os

def run_supersim():
    print("Starting supersim in background mode...")
    process = subprocess.Popen(["supersim", "fork", "--l2.host=0.0.0.0", "--l2.starting.port=4444", "--chains=op,base"], env=os.environ.copy() | dotenv_values(".env"))
    process.wait()

if __name__ == "__main__":
    run_supersim()