import sys, threading, time, socket
from queue import Queue
from pathlib import Path
from multiprocessing.connection import Listener, Client
sys.path.append(str(Path.home()) + '/github/Experiments')
from ExpUtils.TriggerObject import TriggerObject


class Connector:
    def __init__(self, host, port, timeout=1):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, message):
        if not isinstance(message, dict):
            message = {message: None}
        self.conn.send(message)
        print('Sent Data!')

    def receive(self):
        if self.conn.poll():
            data = self.conn.recv()
            if data == 'ping':
                self.conn.send('echo')
                return False
            else:
                print('Received Data!')
                return data
        else:
            return False

    def close(self):
        self.conn.close()


class Master(Connector):
    def connect(self):
        try:
            self.conn_socket = Listener((self.host, self.port))
            self.conn_socket._listener._socket.settimeout(3)
            self.conn_socket._listener._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.conn = self.conn_socket.accept()
            print('Connected by client', self.conn_socket.last_accepted)
            return True
        except:
            self.conn_socket.close()
            time.sleep(1)
            return False


class Slave(Connector):
    def connect(self):
        try:
            self.conn = Client((self.host, self.port))
            self.conn.send('ping')
            if self.conn.recv() == 'echo':
                print('Connected to server', self.host)
                return True
            else:
                time.sleep(1)
                return False
        except:
            time.sleep(1)
            return False


class Communicator:
    def __init__(self, role='server', host='localhost', port=50007, timeout=1, connect_callback=[]):
        self.sendQ = Queue(maxsize=1)
        self.receiveQ = Queue(maxsize=1)
        self._callbacks = dict()
        self._callbacks['close'] = self.close

        # setup send socket
        if role == 'server':
            self.tcp = Master(host, port, timeout)
        elif role == 'client':
            self.tcp = Slave(host, port, timeout)

        # set in/out threads
        self.connected = TriggerObject(initial_value=False, callback=connect_callback)
        self.thread_end = threading.Event()
        self.thread_runner = threading.Thread(target=self.transmitter) 
        self.thread_runner.start()

    def transmitter(self):
        while not self.thread_end.is_set():
            try:
                # connect if not connected
                if not self.connected.value:
                    #print('Trying to connect')
                    self.connected.value = self.tcp.connect()
                else:
                    # read available messages and put them in a queque
                    message = self.tcp.receive()
                    if message:
                        if not any(x in self._callbacks for x in message):
                            print('Message not recognized')
                            print(message)
                            if self.receiveQ.full():
                                self.receiveQ.get()
                            self.receiveQ.put(message)
                        else:
                            for key in message:
                                if key in self._callbacks:
                                    self._callbacks[key](message)
                    
                     # send queued messages
                    if not self.sendQ.empty():
                        message = self.sendQ.get()
                        self.tcp.send(message)
                        print('Message sent!')

                time.sleep(.1)
            except EOFError:
                self.connected.value = False
                self.tcp.close()
            except:
                self.thread_end.set()
                print("Unexpected error:", sys.exc_info()[0])
                self.close()
                time.sleep(.5)
                raise

    def register_callback(self, key):
        self._callbacks.update(key)

    def send(self, message):
        if self.sendQ.full():
            self.sendQ.get()
        self.sendQ.put(message)

    def read(self, nowait=True):
        if not self.receiveQ.empty():
            return self.receiveQ.get()
        elif nowait:
            return False
        else:
            while self.receiveQ.empty():
                time.sleep(.1)
            return self.receiveQ.get()

    def quit(self):
        if self.connected.value:
            self.tcp.send('close')
        self.close()

    def close(self, *args):
        self.thread_end.set()
        if self.connected.value:
            self.tcp.close()
        self.connected.value = False