import os
from functools import wraps
import config
import glob
import telebot


bot = telebot.TeleBot(config.api_key)
users = []


def auth_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if args[0].from_user.username not in users:
            print('user', args[0].from_user.username)
            print(users)
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
                ret[slave] = 'HARDWARE_ERROR'

            else:
                pos = lines[1].find('t=')
                ret[slave] = float(lines[1][pos + 2:]) / 1000.0 if pos != -1 else 'READ_ERROR'

    return ret if ret else {'Error': 'no sensors found'}


def main():
    os.system('sudo modprobe w1-gpio')
    os.system('sudo modprobe w1-therm')

    with open(config.users_file, 'r') as f:
        for user in f.readlines():
            users.append(user.replace('\n', ''))


if __name__ == '__main__':
    main()


@bot.message_handler(commands=['start'])
@auth_required
def start(message):
    bot.send_message(message.chat.id, '/status or /s for status')


@bot.message_handler(commands=['status', 's'])
@auth_required
def status(message):
    info = read()
    bot.send_message(message.chat.id, '\n'.join([key + ': ' + info[key] for key in info.keys()]))


bot.polling()
