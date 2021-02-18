import time
import requests
import json
import socket
from threading import Thread
import tkinter as tk
import tkinter.font as tkFont
from tkinter import messagebox
from os.path import expanduser, isfile, join, abspath
from os import mkdir, getcwd
import webbrowser
from sys import platform, maxsize

version = "v1.0.0"


def resource_path(relative_path):
    try:
        from sys import _MEIPASS
        base_path = _MEIPASS
    except Exception:
        base_path = abspath(".")
    return join(base_path, relative_path)


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
        self.failed = False

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
            self.disconnect()

        self.socket = socket.socket()
        fails = 0
        for i in range(3):
            #print("Connection attempt "+str(i+1))
            try:
                self.status = "connecting"
                self.socket.connect((addr, port))
                break
            except:
                fails += 1
        if fails == 3:
            #print("Connection failed")
            self.failed = True
        else:
            self.status = "stopped"
            self.recvLoopThread = Thread(target=self.recvLoop)
            self.recvLoopThread.start()

    def disconnectionEvent(self):
        self.status = "disconnected"
        #print("Disconnected")
        try:
            self.socket.close()
        except:
            pass
    
    def getFailed(self):
        if self.failed:
            self.failed = False
            return True
        else:
            return False

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
            pass#print("Already disconnected.")

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


class TimerWindow(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)

        self.parent = parent
        self.connectMenu = None
        self.parent.protocol("WM_DELETE_WINDOW", self.exit)

        self.parent.bind('c', self.openConnectMenu)
        self.parent.bind('d', self.disconnect)

        self.timerClient = TimerClient()
        self.font = tkFont.Font(self, ("Arial", 50))

        self.defaultOptions = {"display": {
            "name": "Arial", "size": 50, "color": "#ffffff", "bg": "#000000"}, "lastConnect": ""}
        self.text = tk.Label(self, text=self.convertSeconds(0), font=self.font,width=50,anchor="w")
        self.text.pack()

        if "win" in platform:
            self.optionsFolderPath = expanduser(
                "~/AppData/Roaming/.cooptimer/")
            self.optionsPath = expanduser(
                "~/AppData/Roaming/.cooptimer/options.json")
        else:
            self.optionsFolderPath = getcwd()
            self.optionsPath = join(getcwd(), "options.json")

        self.optionsJson = None
        self.loadSettings()

        self.after(0, self.loop)
    
    def disconnect(self,x=0):
        self.timerClient.disconnect()

    def openConnectMenu(self,x=0):
        if self.connectMenu == None:
            self.connectMenu = ConnectMenu(self)
    
    def exit(self):
        self.timerClient.disconnect()
        self.destroy()
        self.parent.destroy()

    def loop(self):
        self.after(int(1000/65), self.loop)

        if self.timerClient.getFailed():
            messagebox.showerror(message="Connection Failed")
            self.openConnectMenu()

        if self.timerClient.isConnected():
            self.font.config(size=self.optionsJson["display"]["size"])
            self.text.config(text=self.convertSeconds(
                self.timerClient.getTime()))
        else:
            self.font.config(size=int(self.optionsJson["display"]["size"]/2.5))
            self.text.config(text="Press 'c' to connect to a server.")

    def loadSettings(self):
        if not isfile(self.optionsPath):
            try:
                mkdir(self.optionsFolderPath)
            except:
                pass
            with open(self.optionsPath, "w+") as optionsFile:

                self.optionsJson = self.defaultOptions
                json.dump(self.defaultOptions, optionsFile, indent=4)
                optionsFile.close()
        else:
            with open(self.optionsPath, "r") as optionsFile:
                self.optionsJson = json.load(optionsFile)
                optionsFile.close()
        self.validateOptions()
        displayJson = self.optionsJson["display"]
        self.parent.config(background=displayJson["bg"])
        self.config(background=displayJson["bg"])
        self.text.config(background=displayJson["bg"], fg=displayJson["color"])
        self.font.config(family=displayJson["name"])

    def validateOptions(self):
        for i in self.defaultOptions:
            try:
                self.optionsJson[i]
            except:
                self.optionsJson[i] = self.defaultOptions[i]

    @staticmethod
    def convertSeconds(x):
        if x < 0:
            x = 0

        Seconds = "%.3f" % (x-(int(x)-(int(x) % 60)))
        if x % 60 < 10:
            Seconds = "0" + Seconds
        Minutes = str(int(x/(60)) % 60)
        Hours = str(int(x/(60*60)))

        if len(Minutes) < 2 and Hours != "0":
            Minutes = "0" + Minutes

        return ((Hours+":") if Hours != "0" else "")+Minutes+":"+Seconds


class ConnectMenu(tk.Toplevel):
    def __init__(self, parent):
        tk.Toplevel.__init__(self, parent)
        self.parent = parent
        self.protocol("WM_DELETE_WINDOW", self.exit)
        self.inputbox = tk.Entry(self,width=20)
        self.inputbox.grid(column=0,row=0,padx=2,pady=2)
        self.inputbox.insert(0,self.parent.optionsJson["lastConnect"])
        self.button = tk.Button(self,text="Connect",command=self.connect,width=8)
        self.button.grid(column=1,row=0,padx=2,pady=2)

    def exit(self):
        self.parent.connectMenu = None
        self.destroy()
    
    def connect(self):
        output = self.inputbox.get().replace(" ","").rstrip()
        self.parent.optionsJson["lastConnect"] = output

        args = output.split(":")

        if len(args) == 0:
            pass
        else:
            valid = False
            if len(args) == 1:
                args.append(25564)
                valid = True
                
            else:
                try:
                    args[1] = int(args[1])
                    valid = True
                except:
                    messagebox.showerror(message="Invalid Port!")
                    
            if valid:
                self.parent.connectMenu = None
                self.destroy()
                self.parent.timerClient.connect()


if __name__ == "__main__":
    root = tk.Tk()
    root.title("Coop Timer Client "+version)
    root.geometry("400x90")
    try:
        root.iconbitmap(resource_path("Icon.ico"))
    except:
        pass
    tw = TimerWindow(root)
    tw.grid(padx=2, pady=2, row=0, column=0, sticky="w")
    root.mainloop()
