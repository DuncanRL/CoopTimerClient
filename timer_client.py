import time
import requests
import json
import socket
from threading import Thread
import tkinter as tk


class SyncedTime:
    def __init__(self):
        self.resync()

    def resync(self):
        webinfo = json.loads(requests.get(
            "http://worldtimeapi.org/api/timezone/Europe/London").content.decode())
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
        if self.status in ["disconnected", "connecting", "stopped"]:
            return 0
        elif self.status == "paused":
            return self.pauseTime
        elif self.status == "running":
            return self.syncedTime.time()-self.startTime

    def isConnected(self):
        if self.status in ["disconnected", "connecting"]:
            return False
        else:
            return True

    def connect(self, addr="127.0.0.1", port=25564):
        if self.socket != None:
            self.socket.close()
        self.socket = socket.socket()

        fails = 0
        for i in range(3):
            print("Connection attempt "+str(i+1))
            try:
                self.status = "connecting"
                self.socket.connect((addr, port))
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

    def startTimeEvent(self):
        pass  # Play sound?

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

                if msg == "end":
                    self.disconnectionEvent()
                    break
                else:
                    args = msg.split(":")
                    if args[0] == "stop":
                        self.status = "stopped"
                    elif args[0] == "paused":
                        self.status = "paused"
                        self.pauseTime = float(args[1])
                    elif args[0] == "running":
                        if self.status == "stopped":
                            self.startTimeEvent()
                        self.status = "running"
                        self.startTime = float(args[1])

            except ValueError:
                self.disconnectionEvent()
                break


mtc = TimerClient()

mtc.connect()

while True:
    time.sleep(0.1)
    if mtc.isConnected():
        print(mtc.getTime())
