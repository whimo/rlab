import os
from functools import wraps
import config
import glob
from threading import Thread
import telebot
import time


bot = telebot.TeleBot(config.api_key)
users = []
sensors = {}
critical_temp = 0
secret_key = ''


def auth_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if args[0].from_user.username not in users and args[0].chat.id not in users:
            bot.send_message(args[0].chat.id, 'Auth required')
            return -1

        return func(*args, **kwargs)
    return decorated_function


def read():
    slaves = glob.glob(config.basedir + '28*/w1_slave')
    ret = {}
    for slave in slaves:
        with open(slave, 'r') as f:
            lines = f.readlines()

            if lines[0].strip()[-3:] != 'YES':
                ret[slave] = 'HARDWARE ERROR'

            else:
                pos = lines[1].find('t=')
                sensor_id = slave.split('/')[-2]
                ret[sensors[sensor_id].replace('\n', '') if sensor_id in sensors else sensor_id] =\
                    round(float(lines[1][pos + 2:]) / 1000.0, 1) if pos != -1 else 'READ ERROR'

    return ret if ret else {'Error': 'no sensors found'}


def main():
    global users
    global sensors
    global critical_temp
    global secret_key

    os.system('sudo modprobe w1-gpio')
    os.system('sudo modprobe w1-therm')

    with open(os.path.join(config.homedir, config.users_file), 'r') as f:
        for user in f.readlines():
            if 'SECRET_KEY' in user:
                secret_key = user.split()[1]
            else:
                try:
                    users.append(int(user.replace('\n', '')))
                except ValueError:
                    users.append(user.replace('\n', ''))

    with open(os.path.join(config.homedir, config.sensors_file), 'r') as f:
        for sensor_info in f.readlines():
            data = sensor_info.split(' ')
            if not data:
                continue

            if data[0] == 'CRITICAL_TEMP':
                critical_temp = int(data[1])

            sensors[data[0]] = data[1]


if __name__ == '__main__':
    main()


@bot.message_handler(commands=['start'])
@auth_required
def start(message):
    bot.send_message(message.chat.id, '/status or /s for status')


@bot.message_handler(commands=['auth'])
def auth(message):
    if message.chat.id not in users:
        if secret_key in message.text:
            with open(os.path.join(config.homedir, config.users_file), 'a') as f:
                f.write(str(message.chat.id) + '\n')

            bot.send_message(message.chat.id, 'Success! /status or /s for status')
            users.append(message.chat.id)

        else:
            bot.send_message(message.chat.id, 'Bad key, fuck off')

    else:
        bot.send_message(message.chat.id, 'Already authenticated')


@bot.message_handler(commands=['status', 's'])
@auth_required
def status(message):
    info = read()
    bot.send_message(message.chat.id, '\n'.join([key + ': ' + str(info[key]) + 'C' for key in sorted(info.keys())]))


def poll():
    while True:
        try:
            bot.polling()

        except Exception:
            time.sleep(5)
            continue


thread = Thread(target=poll)
thread.setDaemon(True)
thread.start()

criticals = {}

while True:
    for sensor in criticals:
        if criticals[sensor] % 6 == 1:
            for user in users:
                try:
                    bot.send_message(int(user),
                                     'CRITICAL TEMPERATURE on sensor {}: {}C'.format(sensor, read()[sensor]))
                except Exception:
                    pass

        criticals[sensor] += 1

    info = read()
    for sensor in info:
        if info[sensor] >= critical_temp and sensor not in criticals:
            criticals[sensor] = 1

        if info[sensor] < critical_temp and sensor in criticals:
            criticals.pop(sensor, None)

    time.sleep(30)
