import socket
import os
import threading
import pickle
import signal
import json


CommParams = None


class Client(): 
    '''
    Handles each client socket
    '''
    def __init__(self, clt_sckt:socket, addr) -> None:
        self.name = ''
        self.client_socket = clt_sckt
        self.addr = addr
        self.data = None
        self.receiving_thread = None
        self.id = None
        self.recv_thread = None
        # Determines if we have already used this command
        self._finished = False
        global CommParams

    def init_recv_thread(self):
        self.receiving_thread = threading.Thread(target=self.read_message)
        self.receiving_thread.start()
    
    def send_message(self, mssg, encode=True):
        print("sending message")
        if encode:
            self.client_socket.send(mssg.encode())
        else:
            self.client_socket.send(mssg)

    def receive_message(self, decode=True):
        print("waiting for mss2")
        if decode:
            mss = self.client_socket.recv(1024)
            print(f'The message is {mss}')
            return mss.decode()
        else:
            return self.client_socket.recv(1024)
    
    def set_name(self, name):
        self.name = name
    
    def close_socket(self):
        self.client_socket.close()
    
    def set_id(self, id):
        self.id = id

    def read_message(self):
        #print("something")
        while not self._finished:
            data = self.client_socket.recv(4096)
            # self.lock.acquire()
            if self.name == CommParams['STATES']['SLAVE']:
                self.data = data
                #print("message from slave")
            else:
                self.data = data.decode()
                print("message from verifai")
                
            #print(self.data)
            # self.lock.release()
        

    def __del__(self):
        self._finished = True
        if self.receiving_thread:
            self.receiving_thread.join()
        self.close_socket()

class VerifaiConnectionHandler():
    #VerifAI requires a main connection and a controller connection
    def __init__(self, RunningClient:Client, MainVerifAIClient:Client) -> None:

        self.mainClient = MainVerifAIClient
        self.controllerClient = RunningClient
        self.state = None

    def sendControlCommands(self):
        data = self.controllerClient.data
        print(f"----------Sending control data from VerifAI:")
        self.mainClient.send_message(data, False)

    def sendMainMessage(self, message):
        print(f"----------Sending Main Message from VerifAI: {message}")
        self.mainClient.send_message(message, True)
    
    def recieveMessage(self):
        msgg = self.controllerClient.receive_message()
        print(f"----------Recieving Message from controller")
        return msgg
    def recieveVerifAIMessage(self):
        print("waiting for mss1 Verifai")
        msgg = self.mainClient.receive_message()
        print(f"----------Recieving Message from VerifAI")
        return msgg
    
    def initialize_controller(self):
        for _ in range(100):
            self.controllerClient.send_message("init")
        print(f"We are sending the ready command to the controller")
        self.controllerClient.send_message("ready")
    
    
    def __del__(self):
        del self.mainClient

    def set_state(self, state):
        self.state = state



class SynchBridge():

    def __init__(self) -> None:
        global CommParams
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # LB_c: changes for verifai integration 
        print(f" Connecting to localhost {CommParams['HOST']} on designated port {CommParams['PORT']}")
        self.socket.bind((CommParams['HOST'], CommParams['PORT']))
        self.socket.listen()
        print(f"Success!! Listening.......")
        self.controller_clients:[socket] = [] 
        self.verifai_clients:socket = []
        self.master_client:socket = None

        self.verifaConnections:VerifaiConnectionHandler = []

    def createConnection(self):
        '''
        Accept and create a single connection 
        '''
        clt_socket, addr = self.socket.accept()
        client = Client(clt_socket, addr)
        return client
    
    def checkVerifAIState(self):
        '''
        Check message from main VerifAI thread
        '''
        mssg = self.master_client.receive_message()
        finish = False
        if mssg != CommParams['RUN_SIMULATION']:
            finish = True
        print("Is the process finish? ", finish)
        return finish
    
    def continueVerifAIMainThread(self):
        '''
        Send the main VerifAI thread the continue and its subs too.
        '''

        self.master_client.send_message(CommParams['STATES']['CONTINUE'])
        if self.controller_clients:
            for client in self.controller_clients:
                client.send_message(CommParams['STATES']['CONTINUE'])


    def set_role(self, client:Client):
        '''
        Determines the clients role and id 

        assumes receiving message has the format role;id
        '''

        if client.id is None:

            client.send_message(CommParams['STATES']['CONTINUE'])
            init_mssg = client.receive_message()
            init_mssg = init_mssg.split(';')
            role = init_mssg[0]
            id = init_mssg[1]
            client.set_id(id)
            client.set_name(role)
            if role == CommParams['STATES']['SLAVE']:
                
                client.init_recv_thread()
                self.controller_clients.append(client)
            elif role == CommParams['CLIENTS']['VERIFAI_MASTER']: # Init the master thread as soon as we know it is the master
                self.master_client = client
            else:
                self.verifai_clients.append(client)
            print(f"Assigned role to new client its name is {role}")
            print(f"Assigned id to new client its id is {id}")
        

    def connectClients(self, maxClients):
        '''
        Manage all clients and add connections
        '''
        print(f"Waiting for {maxClients} clients")
        n_clnts = 0
        while n_clnts < maxClients:
            client = self.createConnection()
            self.set_role(client)
            n_clnts += 1
            print(f'connected client: {client.name}')
            print('Client number', maxClients, n_clnts)
        #self.continueMessage()
    
    def continueMessageControllers(self):
        '''
        Sends continue signal to the outside controllers (Autoware/Apollo)
        '''
        print(CommParams["STATES"]["CONTINUE"])
        print("in controller clients")
        for client in self.controller_clients:
            print("this is the client", client)
            client.send_message(CommParams["STATES"]["CONTINUE"])
    
    def continueVerifAIController(self):
        '''
        Sends continue message to verifAI controller
        '''

        for client in self.verifai_clients:
            client.send_message(CommParams["STATES"]["CONTINUE"])
    

    def createVerifAIConnectionHandler(self):
        '''
        Creates the connection between VerifAI and the external controller
        '''
        print(f"Creating connection between VerifAI")
        connectionH = VerifaiConnectionHandler(self.controller_clients[0], self.verifai_clients[0]) 
        self.verifaConnections.append(connectionH)

    def mainVerifAIThreadStatus(self):
        '''
        Check if the main thread is still going
        '''

        masterMessage = self.master_client.receive_message()
        if masterMessage == CommParams["STATES"]["RUN_SIMULATION"]:
            finished = False
        else: 
            finished = True
        print("The current process is", finished )
        return finished
    
    def getFinishStep(self):
        '''
        Checks if all verifai controllers have finish the iteration
        '''
        next_step = True
        for connection in self.verifaConnections:
            print('in for')
            currentState = connection.recieveVerifAIMessage()
            connection.set_state(currentState)
            if currentState == CommParams["STATES"]["WAITING_FOR_DATA"]:
                next_step = next_step and True
            else:
                next_step = next_step and False
        return next_step
    
    def makeStep(self):
        '''
        Checks the state of the controllers and sends the continue order
        '''
        next_step = self.getFinishStep()
        # If arrived here, all VerifAI instances are ready
        print("making a step")
        if next_step:
            for connection in self.verifaConnections:
                connection.sendControlCommands()
            next_step = self.getFinishStep()
        return next_step
    
    def SendStopSignal(self, finished):
        '''
        Checks if the current simulation if finished and notifies 
        '''
        mssg = CommParams["STATES"]["STOP_SIMULATION"]
        print(f' finish is {finished} and message is {mssg}')
        if not finished:
            mssg = CommParams["STATES"]["RUN_SIMULATION"]
        print(f' finish is {finished} and message is {mssg}')
        for connection in self.verifaConnections:
            connection.sendMainMessage(mssg)
        print("sent:", mssg)

    def finishCurrentIteration(self):
        '''
        Terminates for one iteration and reboot lists
        '''
        for connection in self.verifaConnections:
            del connection
        self.verifai_clients = []
        self.verifaConnections = []
    def __del__(self):
        self.socket.close()
        for connection in self.verifaConnections:
            del connection
        for controller in self.controller_clients: # FIXME: here I am not closing correctly
            del controller
        if self.master_client:
            self.master_client.close_socket()

    

        

def finish(signum, frame, sync):
    print("arrived here")        
    if sync:
        del sync
        exit(1)



def main():
    #Loading Parameters
    global CommParams
    with open('bridgeParams.json') as commandParams:
        CommParams = json.load(commandParams)
    
    print(CommParams['CLIENTS']['VERIFAI_INTSTANCE'])
    sync = None
    try:
        sync = SynchBridge()
        finsih_handler = lambda signum, frame: finish(signum, frame, sync)
        signal.signal(signal.SIGINT, finsih_handler)
        #CommParams['N_CLIENTS']//2 + 1)
        #sync.createVerifAIConnectionHandler()
        sync.connectClients(2)
        print(f"Success! Connection between Main VerifAI and Controller has been made")
        sync.continueVerifAIMainThread()
        
        for i in range(5): 

            sync.connectClients(1)
            print("checkpoint1")
            sync.createVerifAIConnectionHandler()
            print("checkpoint2")
            sync.continueVerifAIController()
            print("checkpoint3")
            # sync.initialize_controllers()
            finished = False
            while not finished:
                print("checkpoint4")
                finished = sync.mainVerifAIThreadStatus()
                print("checkpoint5")
                sync.makeStep()
                print("checkpoint6")
                sync.SendStopSignal(finished)
            print("checkpoint7")
            sync.finishCurrentIteration()

        del sync
    finally:
        if sync:
            del sync

    


if __name__ == "__main__":
    main()
