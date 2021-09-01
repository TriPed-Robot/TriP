from copy import deepcopy
from trip_kinematics.KinematicGroup import KinematicGroup, Transformation
from trip_kinematics.Robot import Robot, inverse_kinematics, forward_kinematics
from casadi import Opti, SX, Function, SX, nlpsol, vertcat
from typing import Dict, List
from trip_kinematics.HomogenTransformationMatrix import TransformationMatrix
import numpy as np
from math import radians, sin, cos


def c(rx, ry, rz):
    A_CSS_P_trans = TransformationMatrix(
        tx=0.265, ty=0, tz=0.014)

    A_CSS_P_rot = TransformationMatrix(
        conv='xyz', rx=rx, ry=ry, rz=rz)

    A_CSS_P = A_CSS_P_trans * A_CSS_P_rot

    T_P_SPH1_2 = np.array([-0.015, -0.029, 0.0965]) * -1
    T_P_SPH2_2 = np.array([-0.015, 0.029, 0.0965]) * -1
    x0, y0, z0 = T_P_SPH1_2
    x1, y1, z1 = T_P_SPH2_2

    A_P_SPH1_2 = TransformationMatrix(
        tx=x0, ty=y0, tz=z0, conv='xyz')
    A_P_SPH2_2 = TransformationMatrix(
        tx=x1, ty=y1, tz=z1, conv='xyz')

    A_c1 = A_CSS_P * A_P_SPH1_2
    A_c2 = A_CSS_P * A_P_SPH2_2

    c1 = A_c1.get_translation()
    c2 = A_c2.get_translation()
    return c1, c2


def p1(theta):
    A_CCS_lsm_tran = TransformationMatrix(
        tx=0.139807669447128, ty=0.0549998406976098, tz=-0.051)

    A_CCS_lsm_rot = TransformationMatrix(
        rz=radians(-338.5255), conv='xyz')  

    A_CCS_lsm = A_CCS_lsm_tran * A_CCS_lsm_rot

    A_MCS1_JOINT = TransformationMatrix(
        rz=theta, conv='xyz')

    A_CSS_MCS1 = A_CCS_lsm * A_MCS1_JOINT

    A_MCS1_SP11 = TransformationMatrix(
        tx=0.085, ty=0, tz=-0.0245)

    A_CCS_SP11 = A_CSS_MCS1 * A_MCS1_SP11

    p1 = A_CCS_SP11.get_translation()
    return p1


def p2(theta):
    A_CCS_rsm_tran = TransformationMatrix(
        tx=0.139807669447128, ty=-0.0549998406976098, tz=-0.051)

    A_CCS_rsm_rot = TransformationMatrix(
        rz=radians(-21.4745), conv='xyz')  

    A_CCS_rsm = A_CCS_rsm_tran*A_CCS_rsm_rot

    A_MCS2_JOINT = TransformationMatrix(
        rz=theta, conv='xyz')

    A_CSS_MCS2 = A_CCS_rsm * A_MCS2_JOINT

    A_MCS2_SP21 = TransformationMatrix(
        tx=0.085, ty=0, tz=-0.0245)

    A_CSS_SP21 = A_CSS_MCS2 * A_MCS2_SP21

    p2 = A_CSS_SP21.get_translation()
    return p2

theta_left  = SX.sym('theta_left')
theta_right = SX.sym('theta_right')
gimbal_x    = SX.sym('gimbal_x')
gimbal_y    = SX.sym('gimbal_y')
gimbal_z    = SX.sym('gimbal_z')

virtual_state  = vertcat(gimbal_x ,gimbal_y ,gimbal_z )
actuated_state = vertcat(theta_left,theta_right)

opts                   = {'ipopt.print_level':0, 'print_time':0}
r                = 0.11
c1, c2           = c(rx=gimbal_x, ry=gimbal_y, rz=gimbal_z)
closing_equation = ((c1-p1(theta_right)).T @ (c1-p1(theta_right)) -r**2)**2+(
                    (c2-p2(theta_left)).T @ (c2-p2(theta_left)) -  r**2)**2


def swing_to_gimbal(state: Dict[str, float], tips: Dict[str, float] = None):
    x_0 = [0,0,0]
    if tips:
        x_0[2] = tips['rx']
        x_0[3] = tips['ry']
        x_0[4] = tips['rz']

    nlp  = {'x':virtual_state ,'f':closing_equation,'p':actuated_state}
    mapping_solver = nlpsol('swing_to_gimbal','ipopt',nlp,opts)
    solution       = mapping_solver(x0 = x_0,p=[state['swing_left'],state['swing_right']])
    sol_vector     = np.array(solution['x'])
    return {'gimbal_joint': {'rx': sol_vector[0][0], 'ry': sol_vector[1][0], 'rz': sol_vector[2][0]}}


def gimbal_to_swing(state: Dict[str,Dict[str, float]], tips: Dict[str, float] = None):
    x_0 = [0,0]
    if tips:
        x_0[0] = tips['swing_left'] 
        x_0[1] = tips['swing_right']
    
    nlp  = {'x':actuated_state ,'f':closing_equation,'p':virtual_state}
    reverse_mapping_solver = nlpsol('gimbal_to_swing','ipopt',nlp,opts)
    solution               = reverse_mapping_solver(x0 = x_0, p=[ state['gimbal_joint']['rx'], state['gimbal_joint']['ry'],state['gimbal_joint']['rz']])
    sol_vector             = np.array(solution['x'])
    return {'swing_left': sol_vector[0][0], 'swing_right': sol_vector[1][0]}


def single_leg(leg_number):
    leg_name = 'leg'+str(leg_number)+'_'
    leg_rotation  = Transformation(name=leg_name+'leg_rotation',
                               values={'rz':radians(120)*leg_number })
    leg_rotation_group = KinematicGroup(name=leg_name+"leg_rotation",virtual_transformations=[leg_rotation])
    A_CSS_P_trans = Transformation(name=leg_name+'A_CSS_P_trans',
                               values={'tx': 0.265, 'tz': 0.014})

    A_CSS_P_rot = Transformation(name=leg_name+'gimbal_joint',
                             values={'rx': 0, 'ry': 0, 'rz': 0}, state_variables=['rx', 'ry', 'rz'])


    def leg_swing_to_gimbal(swing: Dict[str, float], tips: Dict[str, float] = None):
        swing = deepcopy(swing)
        swing['swing_left'] = swing[leg_name+'swing_left']
        del swing[leg_name+'swing_left']
        swing['swing_right'] = swing[leg_name+'swing_right']
        del swing[leg_name+'swing_right']

        gimbal = swing_to_gimbal(swing,tips)

        gimbal[leg_name+'gimbal_joint'] = gimbal['gimbal_joint']
        del gimbal['gimbal_joint']

        return gimbal

    def leg_gimbal_swing(gimbal: Dict[str, float], tips: Dict[str, float] = None):
        gimbal = deepcopy(gimbal)
        gimbal['gimbal_joint'] = gimbal[leg_name+'gimbal_joint']
        del gimbal[leg_name+'gimbal_joint']

        swing = gimbal_to_swing(gimbal,tips)

        swing[leg_name+'swing_left'] = swing['swing_left']
        del swing['swing_left']
        swing[leg_name+'swing_right'] = swing['swing_right']
        del swing['swing_right']

        return swing


    closed_chain = KinematicGroup(name=leg_name+'closed_chain', virtual_transformations=[A_CSS_P_trans,A_CSS_P_rot], 
                              actuated_state={leg_name+'swing_left': 0, leg_name+'swing_right': 0}, 
                              actuated_to_virtual=leg_swing_to_gimbal, virtual_to_actuated=leg_gimbal_swing,parent=leg_rotation_group)

    A_P_LL = Transformation(name=leg_name+'A_P_LL', values={'tx': 1.640, 'tz': -0.037, })

    zero_angle_convention = Transformation(name=leg_name+'zero_angle_convention',
                                       values={'ry': radians(-3)})

    extend_joint = Transformation(name=leg_name+'extend_joint',
                                   values={'ry': 0}, state_variables=['ry'])

    A_LL_Joint_FCS = Transformation(name=leg_name+'A_LL_Joint_FCS', values={'tx': -1.5})


    return [leg_rotation_group,closed_chain, A_P_LL, zero_angle_convention,extend_joint, A_LL_Joint_FCS]

first_leg  = single_leg(0)
second_leg = single_leg(1)
third_leg  = single_leg(2)
triped     = Robot(first_leg+second_leg+third_leg)
triped.set_actuated_state({'leg0_swing_left': 0, 'leg0_swing_right': 0})
