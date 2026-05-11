from flask import Flask, jsonify, render_template, request
from flask_restful import Api, Resource

app = Flask(__name__)
api = Api(app)

tasks = []
lamp_lat = None
lamp_lon = None


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        raise ValueError(f"Неверный формат цвета: {hex_color}")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


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


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template('index.html')
    elif request.method == 'POST':
        command = request.form.get('command', 'не указана')
        color_hex = request.form.get('color_hex', '#ffffff')

        if command == 'gradient':
            # Для градиента сохраняем список из двух RGB-кортежей
            c1 = request.form.get('gradient_color1', '#ff6b6b')
            c2 = request.form.get('gradient_color2', '#4d96ff')
            tasks.append((command, [hex_to_rgb(c1), hex_to_rgb(c2)]))
            print(f"Градиент: {c1} -> {c2}")
        else:
            # Для on/off/color сохраняем один RGB-кортеж
            tasks.append((command, hex_to_rgb(color_hex)))
            print(f"Команда: {command}, Цвет: {color_hex}")

        return render_template('index.html')


api.add_resource(GetTasks, '/get_tasks')
api.add_resource(DeleteTask, '/delete_task/<int:task_id>')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)