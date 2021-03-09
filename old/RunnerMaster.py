#!/usr/bin/env python

import time, os, numpy, datetime
from queue import Queue
import threading, matplotlib, time, random
import numpy as np
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk


class Writer(object):
    def __init__(self, datapath):
        self.datapath = datapath
        self.queue = Queue()
        self.datasets = dict()
        self.thread_end = threading.Event()
        self.thread_runner = threading.Thread(target=self.dequeue)  # max insertion rate of 10 events/sec
        self.thread_runner.start()

    def createDataset(self, dataset, shape, dtype=numpy.int16, compression="gzip", chunk_len=1):
        self.datasets[dataset] = self.h5Dataset(self.datapath, dataset, shape, dtype, compression, chunk_len)

    def append(self, dataset, data):
        self.queue.put({'dataset': dataset, 'data': data})

    def dequeue(self):
        while not self.thread_end.is_set():
            if not self.queue.empty():
                values = self.queue.get()
                with h5py.File(self.datapath, mode='a') as h5f:
                    dset = h5f[values['dataset']]
                    dset.resize((self.datasets[values['dataset']].i + 1,) + self.datasets[values['dataset']].shape)
                    dset[self.datasets[values['dataset']].i] = [values['data']]
                    self.datasets[values['dataset']].i += 1
                    h5f.flush()
            else:
                time.sleep(.1)

    def exit(self):
        while not self.queue.empty():
            time.sleep(.1)
        self.thread_end.set()
        self.thread_runner.join()
        print(self.thread_runner.is_alive())

    class h5Dataset():
        def __init__(self, datapath, dataset, shape, dtype=numpy.uint16, compression="gzip", chunk_len=1):
            with h5py.File(datapath, mode='a') as h5f:
                self.i = 0
                self.shape = shape
                self.dtype = dtype
                h5f.create_dataset(
                    dataset,
                    shape=(0,) + shape,
                    maxshape=(None,) + shape,
                    dtype=dtype,
                    compression=compression,
                    chunks=(chunk_len,) + shape)


class Presenter(object):
    def __init__(self, shape=(600, 600), dtype=numpy.int16):
        self.queue = Queue()
        self.dtype = dtype
        self.shape = shape
        self.window = tk.Tk()
        #self.cam = Camera()

        # Create a queue to share data between process
        # self.q = Queue()
        #self.cam.set_queue(self.queue)
        #self.cam.start()

        # Create and start the simulation process
        # self.stop_event = multiprocessing.Event()

        # self.present=threading.Thread(target=self.simulation)
        # self.present.start()

        self.window.geometry("%dx%d+%d+%d" % (600, 400, 630, 300))
        sv = tk.StringVar()
        sv.trace_add("write", lambda: print(2))
        # create the entries/buttons
        Entry3 = tk.Entry(self.window, textvariable=sv)
        Entry3.place(bordermode=tk.INSIDE, relheight=.08, relwidth=.19, relx=0.795, rely=0.8)

        # create the entries/buttons
        Entry1 = tk.Entry(self.window)
        Entry1.place(bordermode=tk.INSIDE, relheight=.08, relwidth=.19, relx=0.795, rely=0.08)
        Label1 = tk.Label(self.window)
        Label1.configure(text='''Animal ID''')
        Label1.pack()
        Label1.place(bordermode=tk.INSIDE, relheight=.05, relwidth=.19, relx=0.795, rely=0.03)

        Entry2 = tk.Entry(self.window)
        Entry2.place(bordermode=tk.INSIDE, relheight=.08, relwidth=.19, relx=0.795, rely=0.25)
        Label2 = tk.Label(self.window)
        Label2.configure(text='''Session''')
        Label2.pack()
        Label2.place(bordermode=tk.INSIDE, relheight=.05, relwidth=.19, relx=0.795, rely=0.2)

        #btn1 = tk.Button(self.window, text="Rec", command=lambda: self.cam.rec('%s_%s' % (Entry1.get(), Entry2.get())))
        btn1 = tk.Button(self.window, text="Rec", command=print('rec'))
        btn1.pack()
        btn1.place(bordermode=tk.INSIDE, relheight=.15, relwidth=.2, relx=0.79, rely=0.4)

        #btn2 = tk.Button(self.window, text="Stop", command=self.cam.stop)
        btn2 = tk.Button(self.window, text="Stop", command=print('stop'))
        btn2.pack()
        btn2.place(bordermode=tk.INSIDE, relheight=.15, relwidth=.2, relx=0.79, rely=0.6)

        self.window.title("Video Control")
        self.window.minsize(600, 400)
        self.window.mainloop()

    def run(self):
        # Create the base plot
        self.plot()

        # Call a function to update the plot when there is new data
        self.updateplot()
        self.window.mainloop()
        self.quit()
        print('Done')

    def plot(
            self):  # Function to create the base plot, make sure to make global the lines, axes, canvas and any part that you would want to update later
        fig = matplotlib.figure.Figure()
        self.ax = fig.add_axes([0, 0, 1, 1])
        fig.patch.set_visible(False)
        self.ax.axis('off')
        self.canvas = FigureCanvasTkAgg(fig, master=self.window)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack()
        self.canvas.get_tk_widget().place(bordermode=tk.INSIDE, relheight=1, relwidth=.665, relx=0, rely=0)
        self.canvas._tkcanvas.pack()
        self.canvas._tkcanvas.place(bordermode=tk.INSIDE, relheight=1, relwidth=.665, relx=0, rely=0)
        self.frame = self.ax.imshow(np.random.rand(600, 600), cmap='gray', vmin=1, vmax=2 ** 16)

    def updateplot(self):
        result = self.queue.get()
        while self.queue.qsize() > 1:
            result = self.queue.get()
        if 'normal' == self.window.state():
            # here get crazy with the plotting, you have access to all the global variables that you defined in the plot function, and have the data that the simulation sent.
            self.frame.set_data(result)
            self.ax.draw_artist(self.frame)
            self.canvas.draw()
            self.window.after(10, self.updateplot)
        else:
            print('done')

    def simulation(self):
        cam.set_queue(q)
        # cam.start()
        # while not stop_event.is_set() and 'normal' == window.state():
        #    time.sleep(.01)
        # self.quit()
        pass

    def quit(self):
        print('stopping')
        # self.stop_event.set()
        self.cam.stop()
        self.cam.quit()
        print('stopped')
        # self.simulate.kill()


if __name__ == '__main__':
    p = Presenter()
    p.run()



