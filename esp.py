import st7735
from machine import SPI, Pin
import time
import network
import requests

class SmartLamp:
    def __init__(self, ssid, password):
        self.spi = SPI(1, baudrate=33000000, sck=Pin(18), mosi=Pin(23))
        self.cs = Pin(5, Pin.OUT)
        self.dc = Pin(2, Pin.OUT)
        self.rst = Pin(4, Pin.OUT)

        self.led = Pin(21, Pin.OUT)

        self.rst.value(0)
        time.sleep(0.1)
        self.rst.value(1)
        time.sleep(0.1)

        self.tft = st7735.TFT(self.spi, self.dc, self.rst, self.cs)
        self.tft.initb2()
        self.tft.rgb(True)
        self.tft.rotation(1)
        self.tft.fill(self.tft.BLACK)
        time.sleep(0.1)

        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(False)
        time.sleep(0.1)
        self.wlan.active(True)
        self.wlan.connect(ssid, password)

        timeout = 10
        while not self.wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1

        if self.wlan.isconnected():
            print('Подключено к WiFi')
            print('IP:', self.wlan.ifconfig()[0])
        else:
            print('Не удалось подключиться к WiFi')

    def turn_off(self):
        print('Выключение')
        self.tft.fill(self.tft.BLACK)
        self.led.value(0)
        print('Выключено')

    def turn_on(self):
        print('Включение')
        self.tft.fill(self.tft.WHITE)
        self.led.value(1)
        print('Включено')

    def set_lamp_color(self, r, g, b):
        print(f'Устанавливаем цвет {r}, {g}, {b}')
        if self.led.value() == 0:
            self.turn_on()
        self.tft.fill(self.tft.color(int(r), int(g), int(b)))
        print(f'Установлен цвет {r}, {g}, {b}')

    def gradient_rgb(self, color1, color2, steps):
        if steps < 2:
            return [color1]
        result = []
        for i in range(steps):
            r = int(color1[0] + (color2[0] - color1[0]) * i / (steps - 1))
            g = int(color1[1] + (color2[1] - color1[1]) * i / (steps - 1))
            b = int(color1[2] + (color2[2] - color1[2]) * i / (steps - 1))
            result.append((r, g, b))
        return result

    def soft_overflow(self, color1, color2):
        print('soft_overflow')
        overflow_list = self.gradient_rgb(color1, color2, 100)
        color_index = 0
        while True:
            try:
                url = "http://172.20.10.3:5000/get_tasks"
                answer = requests.get(url).json()
                tasks = answer.get('tasks', [])
                if tasks:
                    task_data, index = tasks[0]
                    command = task_data[0]
                    color = task_data[1]
                    print(f'Получена команда: {command}, цвет: {color}')

                    if command == 'gradient':
                        overflow_list = self.gradient_rgb(color[0], color[1], 100)
                        color_index = 0
                        del_url = f"http://172.20.10.3:5000/delete_task/{index}"
                        resp = requests.post(del_url)
                        print(f'Удаление задачи {index}: {resp.status_code}')
                    else:
                        break
                else:
                    try:
                        color = overflow_list[color_index]
                        self.set_lamp_color(color[0], color[1], color[2])
                        color_index += 1
                    except IndexError:
                        overflow_list = overflow_list[::-1]
                        color_index = 0
            except Exception as e:
                print(f'Ошибка в цикле: {e}')

    def dark_detect(self):
        while True:
            try:
                url = "http://172.20.10.3:5000/get_tasks"
                answer = requests.get(url).json()
                tasks = answer.get('tasks', [])
                if tasks:
                    task_data, index = tasks[0]
                    command = task_data[0]
                    color = task_data[1]
                    print(f'Получена команда: {command}, цвет: {color}')

                    if command == 'dark_detect':
                        del_url = f"http://172.20.10.3:5000/delete_task/{index}"
                        resp = requests.post(del_url)
                        print(f'Удаление задачи {index}: {resp.status_code}')
                    else:
                        break
                else:
                    resp = requests.get("http://172.20.10.3:5000/is_dark")
                    is_dark = bool(resp.json()['is_dark'])
                    if is_dark:
                        self.turn_on()
                    else:
                        self.turn_off()
                time.sleep(5)
            except Exception as e:
                print(f'Ошибка в цикле: {e}')
                time.sleep(5)

    def run_scenario(self, intervals):
        print('Запущен сценарий')
        last_active_color = None
        while True:
            # Проверка новых задач (прерывание)
            try:
                url = "http://172.20.10.3:5000/get_tasks"
                answer = requests.get(url, timeout=5).json()
                tasks = answer.get('tasks', [])
                if tasks:
                    task_data, task_index = tasks[0]
                    command = task_data[0]
                    print(f'Получена команда в сценарии: {command}')
                    return
            except Exception as e:
                print(f'Ошибка проверки задач в сценарии: {e}')

            # Получаем локальное время с сервера
            try:
                resp = requests.get('http://172.20.10.3:5000/get_time', timeout=5)
                data = resp.json()
                h, m = data['hour'], data['minute']
                local_minutes = h * 60 + m
            except Exception as e:
                print('Ошибка получения времени с сервера:', e)
                time.sleep(5)
                continue

            active_interval = None
            for interval in intervals:
                try:
                    start_str = interval['start']
                    end_str = interval['end']
                    start_h, start_m = map(int, start_str.split(':'))
                    end_h, end_m = map(int, end_str.split(':'))
                except:
                    continue
                start_min = start_h * 60 + start_m
                end_min = end_h * 60 + end_m

                if start_min <= end_min:
                    if start_min <= local_minutes < end_min:
                        active_interval = interval
                        break
                else:
                    if local_minutes >= start_min or local_minutes < end_min:
                        active_interval = interval
                        break

            if active_interval:
                color = active_interval['color']
                if last_active_color is not None and last_active_color != color:
                    self._smooth_transition(last_active_color, color)
                self.set_lamp_color(color[0], color[1], color[2])
                last_active_color = color
            else:
                self.turn_off()
                last_active_color = None

            time.sleep(5)

    def _smooth_transition(self, start_rgb, end_rgb, steps=100, delay=0.02):
        gradient = self.gradient_rgb(start_rgb, end_rgb, steps)
        for col in gradient:
            self.set_lamp_color(col[0], col[1], col[2])
            time.sleep(delay)


smart_lamp = SmartLamp('iPhone (Алексей)', 'PJipMqy1')
smart_lamp.turn_on()
while True:
    print('ОСНОВНОЙ ЦИКЛ')
    try:
        url = "http://172.20.10.3:5000/get_tasks"
        answer = requests.get(url).json()
        tasks = answer.get('tasks', [])
        if tasks:
            task_data, index = tasks[0]
            command = task_data[0]
            color = task_data[1]
            print(f'Получена команда: {command}, цвет: {color}')

            if command == 'on':
                if smart_lamp.led.value() == 0:
                    smart_lamp.turn_on()
            elif command == 'off':
                smart_lamp.turn_off()
            elif command == 'gradient':
                del_url = f"http://172.20.10.3:5000/delete_task/{index}"
                resp = requests.post(del_url)
                print(f'Удаление задачи {index}: {resp.status_code}')
                smart_lamp.soft_overflow(color[0], color[1])
                continue
            elif command == 'dark_detect':
                del_url = f"http://172.20.10.3:5000/delete_task/{index}"
                resp = requests.post(del_url)
                print(f'Удаление задачи {index}: {resp.status_code}')
                smart_lamp.dark_detect()
                continue
            elif command == 'scenario':
                del_url = f"http://172.20.10.3:5000/delete_task/{index}"
                resp = requests.post(del_url)
                print(f'Удаление задачи {index}: {resp.status_code}')
                smart_lamp.run_scenario(color)
                continue
            elif command == 'color':
                smart_lamp.set_lamp_color(color[0], color[1], color[2])

            del_url = f"http://172.20.10.3:5000/delete_task/{index}"
            resp = requests.post(del_url)
            print(f'Удаление задачи {index}: {resp.status_code}')
    except Exception as e:
        print(f'Ошибка в цикле: {e}')