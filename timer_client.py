import time, requests, json, socket
from threading import Thread

class SyncedTime:
    def __init__(self):
        self.resync()
    
    def resync(self):
        webinfo = json.loads(requests.get("http://worldtimeapi.org/api/timezone/Europe/London").content.decode())
        self.startTime = time.time()
        dt = webinfo["datetime"]
        unix = webinfo["unixtime"]

        mili = float("0"+dt[dt.index("."):dt.index("+")])
        self.startTimeUniversal = unix+mili
        self.offset = self.startTimeUniversal - self.startTime

    def time(self):
        return time.time() + self.offset
    
    def timeSinceResync(self):
        return time.time() - self.startTime


class TimerClient:
    def __init__(self):
        self.socket = None
        self.status = "disconnected"
        self.syncedTime = SyncedTime()
        self.startTime = self.syncedTime.time()
        self.pauseTime = 0.0
    
    def getTime(self):
        if self.status in ["disconnected","connecting","stopped"]:
            return 0
        elif self.status == 
    
    def connect(self,addr="127.0.0.1",port=25564):
        if self.socket != None:
            self.socket.close()
        self.socket = socket.socket()
        
        fails = 0
        for i in range(3):
            print("Connection attempt "+str(i+1))
            try:
                self.status = "connecting"
                self.socket.connect((addr,port))
                break
            except:
                fails += 1
        if fails == 3:
            print("Connection failed")
        else:
            self.status = "stopped"
            self.recvLoopThread = Thread(target=self.recvLoop)
            self.recvLoopThread.start()
    
    def disconnectionEvent(self):
        self.status = "disconnected"
        print("Disconnected")
        try:
            self.socket.close()
        except:
            pass
    
    def disconnect(self):
        if self.status != "disconnected":
            try:
                self.socket.send("quit")
            except:
                pass

            self.disconnectionEvent()
        else:
            print("Already disconnected.")

    def recvLoop(self):
        while True:
            try:
                msg = self.socket.recv(1024).decode()
                print("Received: "+msg)

                if msg == "end":
                    self.disconnectionEvent()
                    break
            except:
                self.disconnectionEvent()
                break


mtc = TimerClient()

mtc.connect()
