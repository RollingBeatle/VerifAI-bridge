import os
import numpy as np
import time
import scenic.simulators.carla.utils.utils as utils
import socket
import pickle

sync_port = 12345 # TODO: move this to a config/json file
ip = '127.0.0.1'
VERIFAI = "VERIFAI"
WAITING_FOR_DATA = 'waiting_data'
CONTINUE = 'continue'
FINISHED_ITER = 'iter_end'
STOP_SIMULATION = 'STOP_SIMULATION'
ASK_FINISH = "ASK_FINISH"
class AutowareControl():
    def __init__(self, set_point, id:str) -> None:
        '''
        The init should send the setpoint to autoware.
        See word file to define the messge
        '''
        
        sock = socket.socket()
        print("connecting to socket")
        sock.connect((ip, sync_port))
        print("waiting for message")
        mssg = sock.recv(1024)
        print("recieved message")
        self.socket = sock
        self.role = VERIFAI
        self.id = id

        init_mssg = self.role + ';' + self.id
        print(f"sending init message: {init_mssg}")
        self.socket.send(init_mssg.encode())

        mssg = sock.recv(1024)

        self.initialized = False
        x = set_point.position[0]
        y = set_point.position[1]
        z = 0
        print("coordinates: ", x ,y)
        rot = utils.scenicToCarlaRotation(set_point.heading )
        [qx, qy, qz, qw] = utils.carla_rotation_to_ros_quaternion_custom(rot)

        mssg = utils.create_goal_message(x, y, z, qx, qy, qz, qw)
        print("Just Init")
        os.system(mssg) # Send goal to autoware
        for _ in range(20):
            print("waiting for route")
            time.sleep(0.01)
        #pass
    
    
    def step(self):
        '''
        The first iteration should engage autoware.
        There are two options: either carla-ros sends the tick 
                                or we need to implement a socket to send info through the net
        '''
        if not self.initialized:
            print("engage in controller")
            engage = "true"
            mssg = utils.create_engage_message(engage)
            os.system(mssg)
            self.initialized = True
            hand_brake = reverse = False
            brake = steer = throttle = manual_gear_shift = gear = 0
        # else:
        print(f"-----Already engaged waiting for data: {WAITING_FOR_DATA}")
        self.socket.send(WAITING_FOR_DATA.encode())
        print('sending message')
        data = self.socket.recv(4096)
        data = pickle.loads(data)
        print("------Data arrived")
        hand_brake = data["hand_brake"]
        brake = data["brake"]
        steer = data["steer"]
        throttle = data["throttle"]
        reverse = data["reverse"]
        manual_gear_shift = data["manual_gear_shift"]
        gear = data["gear"]
        print(data)

        self.socket.send(ASK_FINISH.encode())
        state = self.socket.recv(1024).decode()
        print(f'The state the controller got was: {state}')
        if state == STOP_SIMULATION:
            self.socket.close()
            mssg = utils.create_engage_message("false")
            f'ros2 topic pub /autoware/engage autoware_auto_vehicle_msgs/msg/Engage "engage: false" -1' 
            os.system(mssg)
        time.sleep(0.01)
        return hand_brake, brake, steer, throttle, reverse, manual_gear_shift, gear
