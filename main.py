import time
import sys

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QPushButton, QTextEdit, QVBoxLayout, QWidget,QMainWindow,QApplication
from ui_pyqt import Ui_MainWindow
import pyaudio
import wave
import numpy as np
import struct

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

class Recorder(QObject):
    """
    Must derive from QObject in order to emit signals, connect slots to other signals, and operate in a QThread.
    """

    sig_step = pyqtSignal(np.ndarray)  # return record array for draw chart

    frames=[]

    def __init__(self):
        super().__init__()
        self.__abort = False

    def readData(self,block):
        count = len(block)/2
        format = "%dh"%(count)
        shorts = struct.unpack( format, block )
        return np.array(shorts)

    @pyqtSlot()
    def work(self):
        """
        Pretend this worker method does work that takes a long time. During this time, the thread's
        event loop is blocked, except if the application's processEvents() is called: this gives every
        thread (incl. main) a chance to process events, which in this sample means processing signals
        received from GUI (such as abort).
        """
        thread_name = QThread.currentThread().objectName()
        thread_id = int(QThread.currentThreadId())  # cast to int() is necessary
        print("*  recording")

        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(format=FORMAT,
                                   channels=CHANNELS,
                                   rate=RATE,
                                   input=True,
                                   frames_per_buffer=CHUNK)

        while 1:
            time.sleep(0.05)
            ### record
            data = self.stream.read(CHUNK)
            self.frames.append(data)
            r_data = self.readData(data)

            ###
            self.sig_step.emit(r_data)
            app.processEvents()  # this could cause change to self.__abort
            if self.__abort:
                break

    def abort(self):
        print("* end recording")
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()

        # WAVE_OUTPUT_FILENAME = self.nameText.toPlainText() + ".wav"
        WAVE_OUTPUT_FILENAME = "test1.wav"

        wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(self.pa.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(self.frames))
        wf.close()

        self.__abort = True


class AudioBase(QMainWindow, Ui_MainWindow):

    sig_abort_workers = pyqtSignal()

    def __init__(self, parent=None):

        super(AudioBase, self).__init__(parent)
        self.setupUi(self)
        self.initUi()

        # Make any cross object connections.
        self._connectSignals()
        QThread.currentThread().setObjectName('main')  # threads can be named, useful for log output
        self.__threads = None


    def _connectSignals(self):
        ## TODO : 放btn connect function
        print(' TODO ')
        self.startBtn.clicked.connect(self.startRecord)
        self.stopBtn.clicked.connect(self.abort_workers)

    def initUi(self):
        # PushButton
        self.startBtn.setEnabled(True)
        self.stopBtn.setDisabled(True)
        # GraphicsView
        self.graphicsView.paused = False
        self.graphicsView.logScale = False
        self.graphicsView.showPeaks = False
        self.graphicsView.downsample = True

        self.graphicsView.p1 = self.graphicsView.addPlot()
        self.graphicsView.p1.setLabel('bottom', 'RowData', 'PCM')
        self.graphicsView.p1.setYRange(0,500)

    def get_spectrum(self, data):
        T = 1.0/RATE
        N = data.shape[0]
        Pxx = (1./N)*np.fft.fft(data)
        f = np.fft.fftfreq(N,T)
        Pxx = np.fft.fftshift(Pxx)
        f = np.fft.fftshift(f)
        return f.tolist(), (np.absolute(Pxx)).tolist()

    def startRecord(self):
        self.startBtn.setDisabled(True)
        self.stopBtn.setEnabled(True)

        self.__threads = []

        # create a recorder object
        record = Recorder()
        record_thread = QThread()
        record_thread.setObjectName('record thread')
        self.__threads.append((record_thread, record))  # need to store worker too otherwise will be gc'd

        record.moveToThread(record_thread)

        # get progress messages from worker:
        record.sig_step.connect(self.on_worker_step)

        # control worker:
        self.sig_abort_workers.connect(record.abort)

        # get read to start worker:

        record_thread.started.connect(record.work)
        record_thread.start()  # this will emit 'started' and start thread's event loop

    @pyqtSlot(np.ndarray)
    def on_worker_step(self,r_data):
        # draw gui chart
        f, Pxx = self.get_spectrum(r_data)
        self.graphicsView.p1.plot(x=f, y=Pxx, clear=True)


    @pyqtSlot()
    def abort_workers(self):
        self.sig_abort_workers.emit()
        print('Asking each worker to abort')
        for record_thread, record in self.__threads:  # note nice unpacking by Python, avoids indexing
            record_thread.quit()  # this will quit **as soon as thread event loop unblocks**
            record_thread.wait()  # <- so you need to wait for it to *actually* quit
        self.stopBtn.setDisabled(True)
        # even though threads have exited, there may still be messages on the main thread's
        # queue (messages that threads emitted before the abort):
        print('All threads exited')

if __name__ == '__main__':
    import sys

    app = QApplication(sys.argv)
    app.setApplicationName("Audio Device Test")

    audio = AudioBase()
    audio.show()

    sys.exit(app.exec_())