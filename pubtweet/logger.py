import threading
import datetime

class Logger(object):
    __logger_lock = threading.Lock()
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            with cls.__logger_lock:
                if cls._instance is None:
                    # print('Creating the object')
                    cls._instance = super(Logger, cls).__new__(cls)
                    cls._instance.__initialize()
        return cls._instance


    def __initialize(self):
        self.messages = []
        now = datetime.datetime.now()
        log_file_name_prefix = '{:04}{:02}{:02}_{:02}{:02}{:02}'.format(now.year, now.month, now.day, now.hour, now.minute, now.second)
        self.log_file_name = 'log/log_{}.log'.format(log_file_name_prefix)


    def add(self, msg, save=True):
        with self.__logger_lock:
            self.messages.append(msg)
            if save:
                with open(self.log_file_name, 'a+') as fh:
                    fh.write(msg)
                    if not msg.endswith('\n'):
                        fh.write('\n')


    def get(self, msg):
        '''Called only from main thread'''
        return self.messages.pop(0)
