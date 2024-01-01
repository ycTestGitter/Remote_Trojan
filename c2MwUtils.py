#-----------------------------------------------------------------------------
# Name:        c2MwUtils.py
#
# Purpose:     This module is a untility function module used for the other 
#              c2 server / client modules to store the malicious action emulation 
#              program's data.
#
# Author:      Yuancheng Liu
#
# Version:     v_0.1.1
# Created:     2023/10/10
# Copyright:   Copyright (c) 2023 LiuYuancheng
# License:     MIT License
#-----------------------------------------------------------------------------

from datetime import datetime

# Define all the task state flag here: 
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

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class programRcd(object):
    """ A object to record the controlled malware's data, YC: Later this module will 
        be replaced by backend data base.
    """

    def __init__(self, uniqid, ipaddr, taskList=None, srvFlag=False) -> None:
        """ Init example :
            malwarercd = programRcd('testMalware', '127.0.0.1')
            Args:
                idx (int): record index in the data manager.
                id (str): malware unique ID.
                ipaddress (str): malware ip address.
                tasksList (list(dict()), optional): malare preset task list. Defaults to None.
                srvFlag (bool): flag to identify whehter it is a server record.
                - One task dict() examlpe:
                {
                    'taskID': 1,
                    'taskType': 'upload',
                    'StartT': None,
                    'repeat': 1,
                    'ExPerT': 0,
                    'taskData': [os.path.join(dirpath, "update_installer.zip")]
                },
        """
        self.uniqid = uniqid
        self.ipaddr = ipaddr
        self.srvFlg = srvFlag
        self.taskList = taskList if taskList else []
        self.taskCountDict = {
            'total'     :len(self.taskList),
            'finish'    :0,
            'accept'    :len(self.taskList),
            'pending'   :0,
            'running'   :0, 
            'error'     :0,
            'deactive'  :0
        }
        # Init the list to store the task result and the alst execution result.
        self.taskRstList = []
        self.lastTaskRst = {
            'taskID': 0,
            'state' : TASK_F_FLG,
            'time': '',
            'taskData': 'registered'
        }
        self._initTasksInfo()

    #-----------------------------------------------------------------------------
    def _initTasksInfo(self):
        """ Create the task summary dict and add the tast state in the tasks list."""
        # add the record task state in the task list.
        for task in self.taskList:
            if task['state'] == TASK_P_FLG:
                self.taskCountDict['pending'] += 1
            elif task['state'] == TASK_R_FLG:
                self.taskCountDict['running'] += 1
            elif task['state'] == TASK_E_FLG:
                self.taskCountDict['error'] += 1
            elif task['state'] == TASK_A_FLG:
                self.taskCountDict['accept'] += 1
            elif task['state'] == TASK_F_FLG:
                self.taskCountDict['finish'] += 1
            self.taskRstList.append(None)

    #-----------------------------------------------------------------------------
    def addNewTask(self, taskType, taskData):
        """ Add a new task to the task list. """
        taskInfo = {
            'taskID'    : len(self.taskList),
            'taskType'  : taskType,
            'StartT'    : None,
            'repeat'    : 1,
            'ExPerT'    : 0,
            'taskData'  : taskData,
            'state'     : TASK_P_FLG if self.srvFlg else TASK_A_FLG
        }
        self.taskList.append(taskInfo)
        self.taskCountDict['total'] += 1
        stateKey = 'pending' if self.srvFlg else 'accept'
        self.taskCountDict[stateKey] += 1
        self.taskRstList.append(None)
    
    #-----------------------------------------------------------------------------
    # define all the public-get() function here: 
    
    def getRcdInfo(self):
        """ reutrn a malware record summary info"""
        infoDict = {'id': self.uniqid, 'ipAddr': self.ipaddr}
        infoDict.update(self.taskCountDict)
        return infoDict

    def getTaskInfo(self, taskID):
        """ Return one task's info dict()"""
        for task in self.taskList:
            if task['taskID'] == taskID: return task
        return None

    def getTaskList(self, taskState=None):
        """ return a list of task dict() based on the task state type."""
        if taskState is None: return self.taskList
        resultList = []    
        for task in self.taskList:
            if task['state'] == taskState: resultList.append(task)
        return resultList

    def getTaskRst(self, taskID=None):
        """ return all tasks result if not input task ID, else return task result."""
        if taskID is None: return self.taskRstList
        if 0 <= int(taskID) <= self.taskCountDict['total']:
            return self.taskList[int(taskID)]
        return None

    def getLastTaskRst(self):
        return self.lastTaskRst

    #-----------------------------------------------------------------------------
    # Define all the public-set() function here: 
    def setTaskState(self, idx, state=TASK_F_FLG):
        if 0 <= idx <= len(self.taskList):
            self.taskList[idx]['state'] = state
            return True
        return False

    def setTaskRst(self, idx, rst):
        if 0 <= idx <= len(self.taskRstList):
            self.taskRstList[idx] = rst
            return True
        return False

    def updateTaskRcd(self, taskList):
        for i, task in enumerate(self.taskList):
            for taskDict in taskList:
                if task['taskID'] == taskDict['taskID']:
                    self.taskList[i]['state'] = taskDict['state']
                    self.taskList[i]['StartT'] = taskDict['Time']
                    self.lastTaskRst.update(taskDict)
                    break

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class mwServerRcd(programRcd):
    """ malware record obj use in the C2 server side."""

    def __init__(self, idx, uniqid, ipaddr, taskList=None, srvFlag=True) -> None:
        super().__init__(uniqid, ipaddr, taskList, srvFlag)
        self.idx = idx
        self.lastUpdateT = None
        self.connected = False
        self._initRegister()
        self.updateTime()

    def _initRegister(self):
        for i, task in enumerate(self.taskList):
            if task['taskType'] == RIG_FLG:
                self.connected = True
                self.taskList[i]['state'] = TASK_F_FLG
                return

    def getRcdInfo(self):
        rcdDict = {
            'idx':self.idx,
            'connected': self.connected,
            'updateT': self.lastUpdateT.strftime('%Y-%m-%d %H:%M:%S')
        }
        rcdDict.update(super().getRcdInfo())
        return rcdDict 

    def updateTime(self):
        self.lastUpdateT = datetime.now()

    def updateRegisterT(self):
        if len(self.taskList) > 0:
            self.taskList[0]['StartT'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------    
class mwClientRcd(programRcd):
    """ malware record obj use in the C2 client side."""

    def __init__(self, uniqid, ipaddr, taskList=None, srvFlag=False) -> None:
        super().__init__(uniqid, ipaddr, taskList, srvFlag)

    def addNewTask(self, task):
        self.taskList.append(task)
