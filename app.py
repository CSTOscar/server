from flask import Flask, render_template, session
from flask_socketio import SocketIO, send, emit
from multiprocessing import Value
from datetime import datetime, timedelta 
from uuid import uuid4
import numpy as np, cv2, base64, sys, os

sys.path.append(os.path.abspath('../AbsoluteObject3DMap'))
sys.path.append(os.path.abspath('../models'))
sys.path.append(os.path.abspath('../models/research'))
sys.path.append(os.path.abspath('../models/research/slim'))
from main.main import setup, main

NUM_STEPS = 30

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
sio = SocketIO(app)

cameras = dict()
images = dict()
cnt = Value('i', 0)


@sio.on('start')
def start():
    if len(cameras) >= 2:
        emit('error', {'error': 'Too many cameras'})
    else:
        session['camera_id'] = str(uuid4());
        payload = {'camera_id': session['camera_id']}
        if 'left' not in cameras.values():
            cameras[session['camera_id']] = 'left';
            payload.update({'side': 'left'})
        else:
            cameras[session['camera_id']] = 'right';
            payload.update({'side': 'right'})
        emit('started', payload, json=True)


@sio.on('ready')
def ready():
    print(cameras)
    if len(cameras) == 2:
        cnt.value = 0
        emit('startRecording', {
            'time': (datetime.utcnow() + timedelta(seconds=2)).isoformat(),
            'interval': 250, # in ms
            'steps': NUM_STEPS
        }, broadcast=True)
    else:
        emit('wait')


@sio.on('stop')
def stop():
    emit('stopAll', broadcast=True)
    print('Stopping..')
    


@sio.on('remove')
def remove(data):
    cid = data.get('camera_id')
    if cid in cameras.keys():
        del cameras[cid]
    emit('stopped')


@sio.on('capture')
def capture(data):
    print("Data from: ", data['side'], "on step: ", data['step'])
    step = int(data['step'])
    if data['step'] not in images.keys():
        images[step] = dict()
    arr = np.fromstring(base64.b64decode(data['image']), np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    cv2.imwrite('images/image_{}_{}.jpg'.format(data['side'],data['step']), image)  
    images[step][data['side']] = image
    cnt.value += 1
    if cnt.value == 2 * NUM_STEPS:
        done()


def done():
    imageL = list()
    imageR = list()
    for i in range(0, NUM_STEPS):
        imageL.append(images[i]['left'])
        imageR.append(images[i]['right'])
    setup()
    json_data = main(imageL, imageR)
    sio.emit('recongised', json_data, broadcast=True)
    print(json_data)


if __name__ == "__main__":
    sio.run(app, '0.0.0.0', 8000, use_reloader=True, log_output=True) 
