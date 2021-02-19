import time
import requests
import json
import socket
from threading import Thread
import tkinter as tk
import tkinter.font as tkFont
from tkinter import messagebox
from os.path import expanduser, isfile, join, abspath, getmtime
from os import mkdir, getcwd
import webbrowser
from sys import platform, maxsize
import tkinter.colorchooser as tkColorChooser
from playsound import playsound
import keyboard

version = "v1.0.4"


def readKey(timeout):
    keyr = keyReader()
    key = keyr.readKey(timeout)
    del(keyr)
    return key


class keyReader():
    def readKey(self, timeout):
        self.key = None
        self.rkt = Thread(target=self.readKeyThread)
        self.rkt.start()
        startTime = time.time()

        while time.time() - startTime < timeout and self.key == None:
            time.sleep(0.01)
        return self.key

    def readKeyThread(self):
        self.key = keyboard.read_hotkey(suppress=False)


def resource_path(relative_path):
    try:
        from sys import _MEIPASS
        base_path = _MEIPASS
    except Exception:
        base_path = abspath(".")
    return join(base_path, relative_path)


class NoInternetConnectionException(Exception):
    pass


def getLocalIP():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
    except:
        raise NoInternetConnectionException
    ip = s.getsockname()[0]
    s.close()
    return ip


class TimerClientInstance:
    def __init__(self, parent, c, addr):
        self.parent = parent
        self.clientSocket = c
        self.addr = addr
        self.running = True
        self.thread = Thread(target=self.loop)
        self.thread.start()

    def loop(self):
        try:
            while self.running:
                msg = self.clientSocket.recv(1024)
                if msg.decode() == "quit":
                    self.running = False
                    self.send("end")
        except:
            pass
        self.parent.removeClient(self)

    def send(self, msg):
        self.clientSocket.send(msg.encode())

    def stop(self):
        self.running = False
        self.send("end")
        self.clientSocket.close()


class TimerServer:
    def __init__(self, addr="127.0.0.1", port=25564):
        self.addr = addr
        self.port = port

        self.syncedTime = SyncedTime()
        self.socket = socket.socket()

        self.clients = []
        self.running = False
        self.startTime = self.syncedTime.time()
        self.pauseTime = 0
        self.timerStatus = "stopped"

    def start(self):
        if not self.running:
            self.running = True

            self.socket.bind((self.addr, self.port))
            self.socket.listen(50)

            self.acceptConnectionsThread = Thread(
                target=self.acceptConnectionsLoop)
            self.acceptConnectionsThread.start()

    def startTimer(self):
        if self.timerStatus != "running":
            self.startTime = self.syncedTime.time() - self.pauseTime
            self.timerStatus = "running"
        self.updateClients()

    def resetTimer(self):
        if self.timerStatus != "stopped":
            self.pauseTime = 0
            self.timerStatus = "stopped"
        self.updateClients()

    def pauseTimer(self):
        if self.timerStatus == "running":
            self.pauseTime = self.syncedTime.time()-self.startTime
            self.timerStatus = "paused"
        self.updateClients()

    def togglePause(self):
        if self.timerStatus == "running":
            self.pauseTimer()
        elif self.timerStatus in ["paused", "stopped"]:
            self.startTimer()

    def updateClient(self, client):
        if self.timerStatus == "stopped":
            client.send("stop")
        elif self.timerStatus == "running":
            client.send("running:"+str(self.startTime))
        elif self.timerStatus == "paused":
            client.send("paused:"+str(self.pauseTime))

    def updateClients(self):
        for client in self.clients:
            self.updateClient(client)

    def sendToAll(self, msg):
        for client in self.clients:
            client.send(msg)

    def acceptConnectionsLoop(self):
        while self.running:
            try:
                c, addr = self.socket.accept()
                client = TimerClientInstance(self, c, addr)
                if self.running:
                    self.clients.append(client)
                    print("[Timer Server] Client '"+str(addr)+"' connected.")
                    self.updateClient(client)
            except:
                pass

    def setTime(self, x):
        self.pauseTime = x
        self.startTime = self.syncedTime.time()-x

    def getTime(self):
        if self.timerStatus == "stopped":
            return 0.0
        elif self.timerStatus == "running":
            return self.syncedTime.time()-self.startTime()
        elif self.timerStatus == "paused":
            return self.pauseTime

    def resync(self):
        self.syncedTime.resync()
        self.sendToAll("resync")

    def kill(self):
        for i in self.clients:
            i.stop()
        self.running = False
        self.socket.close()

    def removeClient(self, client):
        print("[Timer Server] Client '"+str(client.addr)+"' disconnected.")
        self.clients.remove(client)


class SyncedTime:
    def __init__(self):
        self.resync()

    def resync(self):
        request = requests.get(
            "http://worldtimeapi.org/api/timezone/Europe/London")
        webinfo = json.loads(request.content.decode())
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
    def __init__(self, parent=None):
        self.parent = parent
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
            self.status = "disconnected"
            self.failed = True
        else:
            self.status = "stopped"
            self.recvLoopThread = Thread(target=self.recvLoop)
            self.recvLoopThread.start()

    def disconnectionEvent(self):
        self.status = "disconnected"
        # print("Disconnected")
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
        try:
            self.parent.startTimeEvent()
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
            pass  # print("Already disconnected.")

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
                    elif args[0] == "resync":
                        self.syncedTime.resync()
                    elif args[0] == "paused":
                        self.status = "paused"
                        self.pauseTime = float(args[1])
                    elif args[0] == "running":
                        wasStopped = False
                        if self.status == "stopped":
                            wasStopped = True
                        self.status = "running"
                        self.startTime = float(args[1])
                        if wasStopped:
                            self.startTimeEvent()

            except:
                self.disconnectionEvent()
                break


class TimerWindow(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        parent.attributes("-topmost", True)

        self.parent = parent
        self.connectMenu = None
        self.fontMenu = None
        self.hostMenuTL = None
        self.parent.protocol("WM_DELETE_WINDOW", self.exit)

        self.timerClient = TimerClient(parent=self)
        self.parent.bind('f', self.openFontMenu)
        self.parent.bind('c', self.openConnectMenu)
        self.parent.bind('d', self.disconnect)
        self.parent.bind('h', self.openHostMenu)
        self.font = tkFont.Font(self, ("Arial", 50))
        self.dingPath = resource_path("ding.mp3")

        self.defaultOptions = {"display": {
            "name": "Arial", "size": 50, "color": "#ffffff", "bg": "#000000"}, "lastConnect": "", "ding": False}
        self.text = tk.Label(self, text=self.convertSeconds(
            0), font=self.font, width=50, anchor="w",)
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

        self.startTimeEvent()

        self.after(0, self.loop)

    def openHostMenu(self, x=0):
        if self.hostMenuTL == None:
            self.hostMenuTL = HostMenuTL(self)

    def startTimeEvent(self):
        try:
            if self.optionsJson["ding"]:
                playsound(self.dingPath, False)
        except:
            pass

    def disconnect(self, x=0):
        if self.timerClient.isConnected():
            ans = messagebox.askyesno(
                title="CTC: Disconnect?", message="Are you sure you want to disconnect?")
            if ans:
                self.timerClient.disconnect()

    def openFontMenu(self, x=0):
        if self.connectMenu == None and self.fontMenu == None:
            self.fontMenu = FontMenu(self)

    def openConnectMenu(self, x=0):
        if self.connectMenu == None and self.fontMenu == None:
            self.connectMenu = ConnectMenu(self)

    def exit(self):
        if not self.hostMenuTL is None:
            self.hostMenuTL.exit()
        self.timerClient.disconnect()
        self.destroy()
        self.parent.destroy()
        self.save()

    def save(self):
        with open(self.optionsPath, "w+") as optionsFile:
            json.dump(self.optionsJson, optionsFile)
            optionsFile.close()

    def loop(self):
        self.after(int(1000/80), self.loop)

        if self.timerClient.getFailed():
            messagebox.showerror(title="CTC: Error",
                                 message="Connection Failed")
            self.openConnectMenu()

        if self.timerClient.isConnected():
            self.font.config(size=self.optionsJson["display"]["size"])
            self.text.config(text=self.convertSeconds(
                self.timerClient.getTime()))
        else:
            if self.timerClient.status == "connecting":
                self.font.config(
                    size=int(self.optionsJson["display"]["size"]/2.5))
                self.text.config(text="Connecting...")
            else:
                self.font.config(
                    size=int(self.optionsJson["display"]["size"]/3))
                self.text.config(
                    text="Press 'c' to connect to a server.\nPress 'd' to disconnect.\nPress 'f' to change font settings.\nPress 'h' to host a server.", anchor="w", justify=tk.LEFT)

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
        self.reloadJson()

    def reloadJson(self):
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
        self.attributes("-topmost", True)
        self.parent = parent
        self.protocol("WM_DELETE_WINDOW", self.exit)
        self.inputbox = tk.Entry(self, width=20)
        self.inputbox.grid(column=0, row=0, padx=2, pady=2)
        self.inputbox.insert(0, self.parent.optionsJson["lastConnect"])
        self.button = tk.Button(self, text="Connect",
                                command=self.connect, width=8)
        self.button.grid(column=1, row=0, padx=2, pady=2)

    def exit(self):
        self.parent.connectMenu = None
        self.destroy()

    def connect(self):
        output = self.inputbox.get().replace(" ", "").rstrip()
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
                    messagebox.showerror(
                        title="CTC: Error", message="Invalid Port!")

            if valid:
                self.parent.connectMenu = None
                self.destroy()
                self.parent.timerClient.status = "connecting"
                self.parent.after(int(1000/60), self.parent.timerClient.connect,
                                  args[0], args[1])


class HostMenuTL(tk.Toplevel):
    def __init__(self, parent):
        tk.Toplevel.__init__(self, parent)
        self.parent = parent
        self.attributes("-topmost", True)
        self.hostMenu = HostMenu(self, containedByClient=True)
        self.hostMenu.grid(row=0, column=0, padx=2, pady=2)

        self.title("Coop Timer Server")
        self.protocol("WM_DELETE_WINDOW", self.exit)

    def exit(self):
        self.hostMenu.close()
        self.parent.hostMenuTL = None
        self.destroy()


class HostMenu(tk.Frame):
    def __init__(self, parent, containedByClient=False, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        parent.attributes("-topmost", True)
        self.parent = parent
        if containedByClient:
            self.timerClient = parent.parent.timerClient

        if "win" in platform:
            self.optionsFolderPath = expanduser(
                "~/AppData/Roaming/.cooptimer/")
            self.optionsPath = expanduser(
                "~/AppData/Roaming/.cooptimer/serverOptions.json")
        else:
            self.optionsFolderPath = getcwd()
            self.optionsPath = join(getcwd(), "serverOptions.json")

        self.defaultOptions = {"mcPath": (expanduser(
            "~/AppData/Roaming/.minecraft" if "win" in platform else "")), "port": 25564, "startKey": "[", "resetKey": "]", "startMessage": "Set the time to 0"}

        self.optionsJson = None
        self.loadSettings()
        self.timerServer = None
        self.localIP = getLocalIP()

        self.startKey = self.optionsJson["startKey"]
        self.resetKey = self.optionsJson["resetKey"]

        pathFrame = tk.Frame(self)
        pathFrame.grid(row=0, column=0, sticky="w", padx=2, pady=2)

        tk.Label(pathFrame, text="Minecraft Path: ").grid(
            row=0, column=0, padx=2, pady=2)
        self.mcPathEntry = tk.Entry(pathFrame)
        self.mcPathEntry.grid(row=0, column=1, sticky="w", padx=2, pady=2)
        self.mcPathEntry.insert(0, self.optionsJson["mcPath"])

        tk.Label(pathFrame, text="/time set 0 >").grid(
            row=2, column=0, padx=2, pady=2)
        self.startMessageEntry = tk.Entry(pathFrame)
        self.startMessageEntry.grid(
            row=2, column=1, sticky="w", padx=2, pady=2)
        self.startMessageEntry.insert(0, self.optionsJson["startMessage"])

        self.startKeyButton = tk.Button(
            self, text="Start/Pause: "+self.startKey, width=14, command=self.setStartKey)
        self.startKeyButton.grid(row=4, column=0, sticky="w", padx=2, pady=2)
        self.resetKeyButton = tk.Button(
            self, text="Reset: "+self.resetKey, width=14, command=self.setResetKey)
        self.resetKeyButton.grid(row=4, column=0, sticky="e", padx=2, pady=2)

        serverStuffFrame = tk.Frame(self)
        serverStuffFrame.grid(row=400, column=0, sticky="w", padx=2, pady=2)

        addrInfoFrame = tk.Frame(serverStuffFrame)
        addrInfoFrame.grid(row=1, column=0, padx=2, pady=2)

        tk.Label(addrInfoFrame, text=f"Local IP: {self.localIP}").grid(
            row=0, column=0, sticky="w", padx=2, pady=2)

        portFrame = tk.Frame(addrInfoFrame)
        portFrame.grid(row=1, column=0, sticky="w", padx=2, pady=2)

        tk.Label(portFrame, text="Port: ").grid(
            row=0, column=0, sticky="w", padx=2, pady=2)
        self.portEntry = IntEntry(portFrame, max=65535)
        self.portEntry.config(width=6)
        self.portEntry.insert(0, str(self.optionsJson["port"]))
        self.portEntry.grid(row=0, column=1, sticky="w", padx=2, pady=2)

        self.button = tk.Button(
            serverStuffFrame, text="Start Server", command=self.buttonPress)
        self.button.grid(row=1, column=1, padx=2, pady=2, sticky="w")

        self.connectedLabel = tk.Label(serverStuffFrame, text="Connected: N/A")
        self.connectedLabel.grid(row=2, column=0, sticky="w", padx=2, pady=2)

        self.after(100, self.loop)

    def loop(self):
        self.after(100, self.loop)
        if self.timerServer == None:
            self.connectedLabel.config(text="Connected: N/A")
        else:
            self.connectedLabel.config(
                text="Connected: "+str(len(self.timerServer.clients)))
            if not self.timerClient.isConnected():
                self.timerClient.connect(
                    self.localIP, int(self.portEntry.get()))

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

    def save(self):
        self.optionsJson["mcPath"] = self.mcPathEntry.get()
        self.optionsJson["startMessage"] = self.startMessageEntry.get()
        self.optionsJson["port"] = int(self.portEntry.get())
        self.optionsJson['startKey'] = self.startKey
        self.optionsJson['resetKey'] = self.resetKey
        with open(self.optionsPath, "w+") as optionsFile:
            json.dump(self.optionsJson, optionsFile)
            optionsFile.close()

    def validateOptions(self):
        for i in self.defaultOptions:
            try:
                self.optionsJson[i]
            except:
                self.optionsJson[i] = self.defaultOptions[i]

    def setStartKey(self, x=0):
        k = readKey(10)
        if not k is None:
            self.startKey = k
            self.startKeyButton.config(text="Start/Pause: "+k)

    def setResetKey(self, x=0):
        k = readKey(10)
        if not k is None:
            self.resetKey = k
            self.resetKeyButton.config(text="Reset: "+k)

    def buttonPress(self):
        if self.timerServer is None:
            self.timerServer = TimerServer(
                addr=self.localIP, port=int(self.portEntry.get()))
            self.button.config(text="Stop Server")
            self.timerServer.start()

            for i in [self.mcPathEntry, self.startMessageEntry, self.portEntry, self.startKeyButton, self.resetKeyButton]:
                i.config(state='disabled')
            try:
                self.shk = keyboard.add_hotkey(
                    self.startKey, self.timerServer.togglePause)
            except:
                pass
            try:
                self.rhk = keyboard.add_hotkey(
                    self.resetKey, self.timerServer.resetTimer)
            except:
                pass

            self.logPath = join(self.mcPathEntry.get(), "logs/latest.log")
            self.lastMTime = getmtime(self.logPath)
            self.startMessage = self.startMessageEntry.get()
            with open(self.logPath, "r") as logFile:
                self.logLineLen = len(logFile.readlines())
                logFile.close()

            self.after(0, self.checkForTSZ)
        else:
            self.timerServer.kill()
            self.timerServer = None
            self.button.config(text="Start Server")
            for i in [self.mcPathEntry, self.startMessageEntry, self.portEntry, self.startKeyButton, self.resetKeyButton]:
                i.config(state='normal')

            keyboard.clear_all_hotkeys()

    def checkForTSZ(self):
        if not self.timerServer is None:
            self.after(50, self.checkForTSZ)
        mtime = getmtime(self.logPath)
        if mtime != self.lastMTime:
            self.lastMTime = mtime
            with open(self.logPath,"r") as logFile:
                lines = [i.rstrip() for i in logFile.readlines()]
                logFile.close()
            for i in lines[self.logLineLen:]:
                if "Set the time to 0" in i:
                    self.timerServer.resetTimer()
                    self.timerServer.startTimer()
            self.logLineLen = len(lines)

    def close(self):
        if not self.timerServer is None:
            self.timerServer.kill()

        self.save()


class FontMenu(tk.Toplevel):
    def __init__(self, parent):
        tk.Toplevel.__init__(self, parent)
        self.attributes("-topmost", True)
        self.after(100, self.loop)
        self.parent = parent
        self.protocol("WM_DELETE_WINDOW", self.exit)

        fontframe = tk.Frame(self)
        fontframe.grid(row=0, column=0, padx=2, pady=2)
        tk.Button(fontframe, text="Open List", command=self.openFontList, width=7).grid(
            padx=2, pady=2, row=0, column=0, sticky="w")
        self.fontEntry = tk.Entry(fontframe, width=19)
        self.fontEntry.insert(0, parent.optionsJson["display"]["name"])
        self.fontEntry.grid(padx=2, pady=2, row=0, column=1, sticky="w")
        self.fontSizeEntry = IntEntry(fontframe, 200)
        self.fontSizeEntry.insert(
            0, str(parent.optionsJson["display"]["size"]))
        self.fontSizeEntry.config(width=3)
        self.fontSizeEntry.grid(padx=2, pady=2, row=0, column=2)

        colorFrame = tk.Frame(self)
        colorFrame.grid(row=1, column=0, padx=2, pady=2)

        self.button1 = tk.Button(colorFrame, width=13,
                                 command=self.chooseColour1)
        self.button2 = tk.Button(colorFrame, width=13,
                                 command=self.chooseColour2)
        self.button1.grid(padx=2, pady=2, row=1, column=0)
        self.button2.grid(padx=2, pady=2, row=1, column=1)

        self.color1 = parent.optionsJson["display"]["color"]
        self.color2 = parent.optionsJson["display"]["bg"]

        self.button1.configure(bg=self.color1)
        self.button2.configure(bg=self.color2)

        self.dingVar = tk.IntVar(
            self, value=1 if parent.optionsJson["ding"] else 0)

        self.dingCheck = tk.Checkbutton(
            self, text="Ding? ", variable=self.dingVar, onvalue=1, offvalue=0)
        self.dingCheck.grid(row=2, column=0)

    def chooseColour1(self):
        self.color1 = tkColorChooser.askcolor(self.color1)[1]
        self.button1.configure(bg=self.color1)
        self.focus()

    def chooseColour2(self):
        self.color2 = tkColorChooser.askcolor(self.color2)[1]
        self.button2.configure(bg=self.color2)
        self.focus()

    def openFontList(self):
        if "win" in platform:
            filename = expanduser(
                "~/AppData/Roaming/.cooptimer/fonts.html")
        else:
            filename = join(getcwd(), "fonts.html")

        with open(filename, "w") as fontfile:
            fontfile.write("<!DOCTYPE html><html><body>")
            for i in tk.font.families(self):
                fontfile.write("<p>"+i+"</p>")
            fontfile.write("</body></html>")
            fontfile.close()

        webbrowser.open(filename)

    def loop(self):
        self.after(100, self.loop)
        self.updatestuff()

    def updatestuff(self):
        self.parent.optionsJson["display"] = {"name": self.fontEntry.get(), "size": int(
            self.fontSizeEntry.get()), "color": self.color1, "bg": self.color2}
        self.parent.optionsJson["ding"] = (self.dingVar.get() == 1)
        self.parent.reloadJson()

    def exit(self):
        self.parent.fontMenu = None
        self.destroy()


class IntEntry(tk.Entry):
    def __init__(self, parent, max=maxsize):
        self.max = max
        self.parent = parent
        vcmd = (self.parent.register(self.validateInt),
                '%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')
        tk.Entry.__init__(self, parent, validate='key', validatecommand=vcmd)

    def validateInt(self, action, index, value_if_allowed,
                    prior_value, text, validation_type, trigger_type, widget_name):
        if value_if_allowed == "":
            return True
        if value_if_allowed:
            try:
                if (len(value_if_allowed) > 1 and value_if_allowed[0] == "0") or (int(value_if_allowed) > self.max):
                    return False
                return True
            except ValueError:
                return False
        else:
            return False


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
