""" Scenario Description
Traffic Scenario 01.
Control loss without previous action.
The ego-vehicle loses control due to bad conditions on the road and it must recover, coming back to its original lane.
"""

from bridge_sync import AutowareControl



## SET MAP AND MODEL (i.e. definitions of all referenceable vehicle types, road library, etc)
param map = localPath('../../../tests/Town01.xodr')
param carla_map = 'Town01'
model scenic.simulators.carla.model
timestep = 0.05
param timestep = timestep
use_autoware = True
param use_autoware = use_autoware

## CONSTANTS
EGO_MODEL = "vehicle.tesla.model3"
EGO_SPEED = 10
REACTION_DISTANCE = Range(5,10)

## DEFINING BEHAVIORS
# EGO BEHAVIOR: Follow lane, and brake after passing a threshold distance to the leading car
behavior EgoBehavior(speed=10):
    try:
        do FollowLaneBehavior(speed)
    interrupt when withinDistanceToObjsInLane(self, REACTION_DISTANCE):
        take SetBrakeAction(1)

behavior autoware_behavior(setpoint, id):
    autoware_control = AutowareControl(setpoint, id)
    while True:
        hand_brake, brake, steer, throttle, reverse, manual_gear_shift, gear = autoware_control.step()
        take  SetHandBrakeAction(hand_brake), SetBrakeAction(brake), SetSteerAction(steer), SetThrottleAction(throttle), SetReverseAction(reverse), SetGearAction(gear) #, SetManualGearShiftAction(manual_gear_shift)

## DEFINING SPATIAL RELATIONS
# Please refer to scenic/domains/driving/roads.py how to access detailed road infrastructure
# 'network' is the 'class Network' object in roads.py

# make sure to put '*' to uniformly randomly select from all elements of the list 'lanes'
lane = Uniform(*network.lanes)

start = OrientedPoint on lane.centerline
# setpoint = OrientedPoint following lane.centerline from start for Range(50, 60)
lane_2 = lane = Uniform(*network.lanes) # This second lane is actually autoware setpoint
setpoint = OrientedPoint on lane_2.centerline


id = "0"
ego = Car at start,
    with blueprint EGO_MODEL,
    with behavior autoware_behavior(setpoint, id)



car2 = Car following roadDirection for Range(10, 20),
    with blueprint EGO_MODEL,
    with behavior EgoBehavior(EGO_SPEED)

debris1 = Cone following roadDirection for Range(50, 60)
debris2 = Cone following roadDirection from debris1 for Range(5, 10)
debris3 = Cone following roadDirection from debris2 for Range(5, 10)

require (distance to intersection) > 50
terminate when (distance from debris3 to ego) > 10 and (distance to start) > 50
