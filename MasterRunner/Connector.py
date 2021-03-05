# !/usr/bin/env python
import sys, threading, time
from queue import Queue
from multiprocessing.connection import Listener, Client


class Connector:
    def __init__(self, host, port, timeout=1):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send(self, message):
        self.conn.send(message)
        print('Sent Data!')

    def receive(self):
        if self.conn.poll():
            data = self.conn.recv()
            if data == 'ping':
                self.conn.send('echo')
                return False
            else:
                return self.conn.recv()
                print('Received Data!')
        else:
            return False

    def close(self):
        self.conn.close()


class Master(Connector):
    def connect(self):
        self.conn_socket =  Listener((self.host, self.port))
        self.conn = self.conn_socket.accept()
        print('Connected by client', self.conn_socket.last_accepted)
        return True


class Slave(Connector):
    def connect(self):
        self.conn = Client((self.host, self.port))
        self.conn.send('ping')
        if self.conn.recv() == 'echo':
            print('Connected to server', self.host)
            return True
        else:
            return False


class Communicator:
    def __init__(self, role='server', host='localhost', port=50007, timeout=1):
        self.sendQ = Queue(maxsize=1)
        self.receiveQ = Queue(maxsize=1)

        # setup send socket
        if role == 'server':
            self.tcp = Master(host, port, timeout)
        elif role == 'client':
            self.tcp = Slave(host, port, timeout)

        # set in/out threads
        self.connected = False
        self.thread_end= threading.Event()
        self.thread_runner = threading.Thread(target=self.transmitter) 
        self.thread_runner.start()

    def transmitter(self):
        while not self.thread_end.is_set():
            try:
                # connect if not connected
                if not self.connected:
                    self.connected = self.tcp.connect()
                else:
                    # read available messages and put them in a queque
                    message = self.tcp.receive()
                    if message == 'close':
                        self.close()
                    elif message:
                        if self.receiveQ.full():
                            self.receiveQ.get()
                        self.receiveQ.put(message)
                        print('Received message')
                        print(message)
                    
                     # send queued messages
                    if not self.sendQ.empty():
                        message = self.sendQ.get()
                        self.tcp.send(message)
                        print('Message sent!')

                time.sleep(.1)
            except EOFError:
                self.connected = False
                self.tcp.close()
            except:
                self.thread_end.set()
                print("Unexpected error:", sys.exc_info()[0])
                self.close()
                time.sleep(.5)
                raise

    def send(self, message):
        if self.sendQ.full():
            self.sendQ.get()
        self.sendQ.put(message)

    def read(self):
        if self.receiveQ.empty():
            return False
        else:
            return self.receiveQ.get()

    def quit(self):
        self.tcp.send('close')
        self.close()

    def close(self):
        self.connected = False
        self.thread_end.set()
        self.tcp.close()