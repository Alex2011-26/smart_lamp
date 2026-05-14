from flask import Flask, jsonify, render_template, request, redirect, url_for
from flask_restful import Api, Resource
from datetime import datetime
from timezonefinder import TimezoneFinder
import pytz
import ephem

app = Flask(__name__)
api = Api(app)

tasks = []
scenarios = []
lamp_lat = 55.422292
lamp_lon = 86.237869


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        raise ValueError(f"Неверный формат цвета: {hex_color}")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def is_dark(lat, lon):
    """Возвращает True, если сейчас темно (после заката и до рассвета)."""
    if lat is None or lon is None:
        return None

    try:
        # Определяем часовой пояс
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=lat, lng=lon)
        if not tz_name:
            tz_name = 'UTC'
        tz = pytz.timezone(tz_name)
        now = datetime.now(tz)

        # Настраиваем наблюдателя
        observer = ephem.Observer()
        observer.lat = str(lat)
        observer.lon = str(lon)
        observer.pressure = 0
        observer.horizon = '-0:34'  # стандартный горизонт (с рефракцией)

        # Вычисляем солнечный полдень в UTC
        observer.date = str(now.date())  # сегодняшняя дата
        noon_utc = observer.next_transit(ephem.Sun()).datetime()

        # От полдня ищем ближайший восход (предыдущий) и закат (следующий)
        observer.date = noon_utc
        sunrise_utc = observer.previous_rising(ephem.Sun()).datetime()
        sunset_utc = observer.next_setting(ephem.Sun()).datetime()

        # Переводим в местный часовой пояс
        sunrise = pytz.utc.localize(sunrise_utc).astimezone(tz)
        sunset = pytz.utc.localize(sunset_utc).astimezone(tz)

        dark = now < sunrise or now > sunset

        print(f"[DEBUG] is_dark: now={now.strftime('%Y-%m-%d %H:%M %Z')}, "
              f"sunrise={sunrise.strftime('%Y-%m-%d %H:%M %Z')}, "
              f"sunset={sunset.strftime('%Y-%m-%d %H:%M %Z')}, "
              f"dark={dark}")

        return dark
    except Exception as e:
        print(f"[ERROR] is_dark: {e}")
        return None


class GetTasks(Resource):
    def get(self):
        return jsonify({'tasks': [(task, task_id) for task_id, task in enumerate(tasks)]})


class DeleteTask(Resource):
    def post(self, task_id):
        try:
            tasks.pop(task_id)
            return {'status': 'deleted'}, 200
        except IndexError:
            return {'error': 'not found'}, 404


class GetDark(Resource):
    def get(self):
        dark = is_dark(lamp_lat, lamp_lon)
        if dark is None:
            return jsonify({'is_dark': False, 'error': 'no location set'})
        return jsonify({'is_dark': dark})


@app.route('/', methods=['GET', 'POST'])
def index():
    global lamp_lat, lamp_lon
    print(tasks)
    if request.method == 'GET':
        return render_template('index.html')
    elif request.method == 'POST':
        command = request.form.get('command', 'не указана')

        if command == 'set_location':
            lat = float(request.form.get('latitude', 55.7558))
            lon = float(request.form.get('longitude', 37.6173))
            lamp_lat, lamp_lon = lat, lon
            print(f"Новое местоположение: {lat}, {lon}")
            return render_template('index.html')

        elif command == 'gradient':
            c1 = request.form.get('gradient_color1', '#ff6b6b')
            c2 = request.form.get('gradient_color2', '#4d96ff')
            tasks.append((command, [hex_to_rgb(c1), hex_to_rgb(c2)]))
            print(f"Градиент: {c1} -> {c2}")

        else:
            color_hex = request.form.get('color_hex', '#ffffff')
            tasks.append((command, hex_to_rgb(color_hex)))
            print(f"Команда: {command}, Цвет: {color_hex}")

        return render_template('index.html')


@app.route('/scenario', methods=['GET'])
def scenario_page():
    print(scenarios)
    return render_template('scenario.html', scenarios=scenarios)


@app.route('/scenario/create', methods=['POST'])
def create_scenario():
    starts = request.form.getlist('start_time')
    ends = request.form.getlist('end_time')
    colors = request.form.getlist('color')

    intervals = []
    for s, e, c in zip(starts, ends, colors):
        if s and e:
            intervals.append({
                'start': s,
                'end': e,
                'color': c if c else '#ffffff'
            })

    if intervals:
        scenarios.append({'intervals': intervals})

    return redirect('/scenario')


@app.route('/scenario/delete/<int:index>', methods=['POST'])
def delete_scenario(index):
    if 0 <= index < len(scenarios):
        scenarios.pop(index)
    return redirect('/scenario')


@app.route('/scenario/apply/<int:index>', methods=['POST'])
def apply_scenario(index):
    if 0 <= index < len(scenarios):
        scenario = scenarios[index]
        intervals = []
        for interval in scenario['intervals']:
            rgb = hex_to_rgb(interval['color'])
            intervals.append({
                'start': interval['start'],
                'end': interval['end'],
                'color': rgb
            })
        tasks.append(('scenario', intervals))
    return redirect('/scenario')


@app.route('/get_timezone')
def get_timezone():
    if lamp_lat is None or lamp_lon is None:
        print("[DEBUG] get_timezone: координаты отсутствуют")
        return jsonify({'utc_offset': 0})
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lamp_lat, lng=lamp_lon)
    if not tz_name:
        print("[DEBUG] get_timezone: зона не найдена")
        return jsonify({'utc_offset': 0})
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    offset = now.utcoffset().total_seconds() / 3600
    print(f"[DEBUG] get_timezone: tz={tz_name}, offset={offset}")
    return jsonify({'utc_offset': offset})


@app.route('/get_time')
def get_time():
    if lamp_lat is None or lamp_lon is None:
        print("[DEBUG] get_time: координаты отсутствуют")
        return jsonify({'hour': 0, 'minute': 0})
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lamp_lat, lng=lamp_lon)
    if not tz_name:
        tz_name = 'UTC'
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    print(f"[DEBUG] get_time: tz={tz_name}, time={now.strftime('%H:%M')}")
    return jsonify({
        'hour': now.hour,
        'minute': now.minute
    })


@app.route('/get_time_minutes')
def get_time_minutes():
    if lamp_lat is None or lamp_lon is None:
        return jsonify({'minutes': 0})
    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lamp_lat, lng=lamp_lon)
    if not tz_name:
        tz_name = 'UTC'
    tz = pytz.timezone(tz_name)
    now = datetime.now(tz)
    minutes = now.hour * 60 + now.minute
    return jsonify({'minutes': minutes})


api.add_resource(GetTasks, '/get_tasks')
api.add_resource(DeleteTask, '/delete_task/<int:task_id>')
api.add_resource(GetDark, '/is_dark')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)