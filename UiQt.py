from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt 
import ollama   
import sys
import json
import random
import re
import os
from pynput.keyboard import Key, Listener, KeyCode
Settings = json.load(open("_internal/Settings/settings.json","r",encoding="utf8"))

class Appmanager():
    def __init__(self,chat,window,keylistener,tray):
        self.Chat = chat
        self.Window = window
        self.Listener = keylistener
        self.Tray = tray
        self.Window.resize(500, 100)
        self.Listener.keyPressed.connect(self.Window.getkeys)

        self.Listener.start_monitoring()
        
        self.Window.show()
        self.Chat.Setup(window,tray)
        
class SystemTrayIcon(QtWidgets.QSystemTrayIcon):

    def toggle(self,state =None):
        if state == None:
            self.setIcon(self.icon[int(self.status)])
            self.status = not self.status
        else:
            self.setIcon(self.icon[state])
            self.status = not bool(state)
        
    def __init__(self, icon, parent=None):
        QtWidgets.QSystemTrayIcon.__init__(self,parent=parent)
        menu = QtWidgets.QMenu(parent)
        self.icon=icon
        exitAction = menu.addAction("Exit")
        exitAction.triggered.connect(parent.Killframe)
        self.setContextMenu(menu)
        self.status = False
        self.show()
  
        
class KeyMonitor(QtCore.QObject):
    keyPressed = QtCore.Signal(KeyCode)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.listener = Listener(on_press=self.on_keypress)

    def on_keypress(self, key):
       
        self.keyPressed.emit(key)

    def stop_monitoring(self):
        self.listener.stop()

    def start_monitoring(self):
        self.listener.start()

class Chat():
    def __init__(self):
        self.Timealive = "2m"
        self.lang = Settings["Availablelanguages"][Settings["CurrentLanguage"]]
        self.Model = "Deepseek"+self.lang+":latest"
        
        self.response = None
        self.History =  []
        self.Window = None
        self.tray  = None
        self.CheckState = None
        self.path = "_internal/Modelinfos"
    def Setup(self,Window,tray):
        self.Window = Window
        self.tray = tray
        self.setupmodelfile()
        ollama.pull("Deepseek-r1:14b")
        os.system("ollama create Deepseek"+self.lang+" -f TempModelfile ")
        self.Load()
        self.CheckState = QtCore.QTimer(Window)
        self.CheckState.timeout.connect(self.checkRunning)
        self.CheckState.setInterval(2000)
        self.CheckState.start()
    def setupmodelfile(self):
        os.chdir(self.path)

        with open("Modelfile", "r", encoding="utf8") as f,open("TempModelfile","w+", encoding="utf8") as nf,open("Language.json.","r",encoding="utf8") as Lj:
            js = json.load(Lj)
            ln = js["Languages"][self.lang]["SystemMessage"]
            print(ln)
            line=f.readline()
            while (line!=""):
                if "SYSTEM" in line:
                    nf.write("SYSTEM "+ln+"\n")
                else:
                    nf.write(line)
                line = f.readline()
            f.close()
            nf.close()
            Lj.close()
        return
    def setwindow(self, window):
        self.Window = window
    

    def Load(self):
        ollama.generate(model=self.Model,keep_alive=self.Timealive)


    def Clear(self):
        ollama.generate(model=self.Model,keep_alive=0)
        self.CheckState.stop()

    def Request(self, text):
        self.response = ollama.chat(model=self.Model , messages=[{"role": "user", "content": text},],stream=True,options={"stop": ["<think></think>"]})
        
        self.History.append([text,])
        return self.response
    def checkRunning(self):
        if (ollama.ps().models == []):
            self.tray.toggle(1)

            return False
        else:
            self.tray.toggle(0)
            return True

class MainWindow(QtWidgets.QWidget):
    def __init__(self,ch,parent=None):
        super().__init__()
        self.Chat = ch
        self.setWindowTitle("OVA")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.Popups = []
        self.setMaximumSize(QtCore.QSize(500, 100))
        self.button = QtWidgets.QPushButton("Send")
        self.text = QtWidgets.QTextEdit("Hello World")
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addWidget(self.text)
        self.layout.addWidget(self.button)
        self.toggle = QtGui.QAction("open", self)
        self.toggle.triggered.connect(self.getkeys)
        self.button.clicked.connect(self.openframe)
        

    def openframe(self):
        if self.text.toPlainText() == "":
            return
        self.popup = Popup(self.Chat.Request(self.text.toPlainText()))
        self.popup.show()
        self.Popups.append(self.popup)
    

    
    def Killframe(self):
        self.Clear()
        QtWidgets.QApplication.instance().quit()


    def Clear(self):
        self.Chat.Clear()    
   
    def getkeys(self,key):

        if KeyCode.from_char(key).char == '<79>':
            print("open")
            if self.isHidden():
                self.show()
           
        elif key == Key.esc:
            if self.text.hasFocus():
                print("close")
                self.hide()
        elif key==Key.enter and self.text.hasFocus():
            self.openframe()
        elif not self.Chat.checkRunning():
            self.Chat.Load()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            
            self._move()
            return super().mousePressEvent(e)

    def _move(self):
        window = self.window().windowHandle()
        window.startSystemMove()

    def _resize(self):
        window = self.window().windowHandle()
        window.startSystemResize(Qt.LeftEdge) 


class Popup(QtWidgets.QWidget):
    def __init__(self,stream):
        super().__init__()
        self.text = QtWidgets.QTextEdit(readOnly=True)
        self.stream = stream
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addWidget(self.text)
        self.setFocus()
        self.setWindowIcon(OnIcon)
        self.setWindowTitle("Ova Response")
        self.Timer = QtCore.QTimer(self)
        self.Timer.timeout.connect(self.read)
        self.Timer.setInterval(100)
        self.Timer.start()



    def read(self):
        
        txt = next(self.stream,"empty")
       
        if (txt != "empty"):
            res = re.sub(r'</think>', '', txt['message']['content'], flags=re.DOTALL)
            res= re.sub(r'\"\"\"', '',res, flags=re.DOTALL)
            self.text.setText(self.text.toPlainText() + res)
            self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())
        else: 
            self.Timer.stop()  
            return 



    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.destroy()
   

if __name__ == "__main__":
   
    app = QtWidgets.QApplication([])
    OnIcon = QtGui.QIcon("_internal/icons/IconOVA_on.png")
    OfIcon = QtGui.QIcon("_internal/icons/IconOVA_off.png")
    app.setStyle("Fusion")  
    monitor = KeyMonitor(app)
    
    chat= Chat()
    widget = MainWindow(ch=chat)
    
    trayIcon = SystemTrayIcon([OnIcon,OfIcon], widget)
    main = Appmanager(chat, widget, monitor, trayIcon)
    
    
    

    sys.exit(app.exec())