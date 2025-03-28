import math
import wpilib
import hal
import wpilib.simulation as simlib  # 2021 name for the simulation library
import wpimath.geometry as geo
from wpimath.kinematics._kinematics import SwerveDrive4Kinematics, SwerveModuleState, SwerveModulePosition
from pyfrc.physics.core import PhysicsInterface

from robot import MyRobot
import constants
import simmech as sm
from subsystems.swerve_constants import DriveConstants as dc

class PhysicsEngine:

    def __init__(self, physics_controller: PhysicsInterface, robot: MyRobot):
        # Copied from 2024 code
        self.physics_controller = physics_controller  # must have for simulation
        self.robot = robot

        # 1. create sparkbasesims for each spark in the swerve
        # 2. create flywheelsims for each swerve dof
        # in update sim:
            # calculate flywheel states given sparkbasesim output
            # tell sparkbasesim about the states
                # no abs encoders required for drive motors
                # yes abs encoder required for turn motor
            # tell pyfrc.physics.drivetrain.four_motor_swerve_drivetrain about the states
                # it wants duty cycle, which getAppliedOutput gives


        self.kinematics: SwerveDrive4Kinematics = dc.kDriveKinematics  # our swerve drive kinematics

        # set up LEDs - apparently not necessary - glass gui grabs the default one and you can show it
        # self.ledsim = simlib.AddressableLEDSim()

        # NavX (SPI interface) - no idea why the "4" is there, seems to be the default name generated by the navx code
        self.navx = simlib.SimDeviceSim("navX-Sensor[4]")
        self.navx_yaw = self.navx.getDouble("Yaw")  # for some reason it seems we have to set Yaw and not Angle
        self.navx_angle = self.navx.getDouble("Angle")

        self.analogs = [simlib.AnalogInputSim(i) for i in range(4)]
        self.analog_offsets = []

        # create a dictionary so we can refer to the sparks by name and get their relevant parameters
        self.spark_dict = {}
        # kinematics chassis speeds wants them in same order as in original definition - unfortunate ordering
        self.spark_drives = ['lf_drive', 'rf_drive', 'lb_drive', 'rb_drive']
        self.spark_drive_ids = [21, 25, 23, 27]  # keep in this order - based on our kinematics definition
        self.spark_turns = ['lf_turn', 'rf_turn', 'lb_turn', 'rb_turn']
        self.spark_turn_ids = [20, 24, 22, 26]  # keep in this order

        # Got rid of last year's elements: 'br_crank', 'bl_crank', 'tr_crank', 'tl_crank', 't_shooter', 'b_shooter'
        self.spark_peripherals = ['intake', 'indexer']
        self.spark_peripheral_ids = [5, 12] # Kept  'indexer' id as 12 because it came last before removing the elements

        # allow ourselves to access the simdevice's Position, Velocity, Applied Output, etc
        self.spark_names = self.spark_drives + self.spark_turns + self.spark_peripherals
        self.spark_ids = self.spark_drive_ids + self.spark_turn_ids + self.spark_peripheral_ids
        for idx, (spark_name, can_id) in enumerate(zip(self.spark_names, self.spark_ids)):
            spark = simlib.SimDeviceSim(f'SPARK MAX [{can_id}]')
            position = spark.getDouble('Position')
            velocity = spark.getDouble('Velocity')
            output = spark.getDouble('Applied Output')
            self.spark_dict.update({spark_name: {'controller': spark, 'position': position,
                                                 'velocity': velocity, 'output': output}})
        #for key, value in self.spark_dict.items():  # see if these make sense
            #print(f'{key}: {value}')

        self.distances = [0, 0, 0, 0]

        # set up the initial location of the robot on the field
        self.x, self.y = constants.k_start_x, constants.k_start_y
        self.theta = 0
        initial_pose = geo.Pose2d(0, 0, geo.Rotation2d())
        self.physics_controller.move_robot(geo.Transform2d(self.x, self.y, 0))

        # if we want to add an armsim see test_robots/sparksim_test/
        self.update_elevator_positions()

    def update_sim(self, now, tm_diff):
        simlib.DriverStationSim.setAllianceStationId(hal.AllianceStationID.kBlue2)


        dash_values = ['lf_target_vel_angle', 'rf_target_vel_angle', 'lb_target_vel_angle', 'rb_target_vel_angle']
        target_angles = [wpilib.SmartDashboard.getNumberArray(dash_value, [0, 0])[1] for dash_value in dash_values]
        for spark_turn, target_angle in zip(self.spark_turns, target_angles):
            self.spark_dict[spark_turn]['position'].set(target_angle)  # this works to update the simulated spark
        if constants.k_swerve_debugging_messages:
            wpilib.SmartDashboard.putNumberArray('target_angles', target_angles)

        # send the speeds and positions from the spark sim devices to the fourmotorswervedrivetrain
        module_states = []
        for drive, turn in zip(self.spark_drives, self.spark_turns):
            module_states.append(SwerveModuleState(
                self.spark_dict[drive]['velocity'].value, geo.Rotation2d(self.spark_dict[turn]['position'].value))
            )

        # using our own kinematics to update the chassis speeds
        module_states = self.robot.container.swerve.get_desired_swerve_module_states()
        speeds = self.kinematics.toChassisSpeeds(tuple(module_states))

        # update the sim's robot
        self.physics_controller.drive(speeds, tm_diff)

        self.robot.container.swerve.pose_estimator.resetPosition(gyroAngle=self.physics_controller.get_pose().rotation(), wheelPositions=[SwerveModulePosition()] * 4, pose=self.physics_controller.get_pose())

        #
        # # send our poses to the dashboard so we can use it with our trackers
        # pose = self.physics_controller.get_pose()
        # self.x, self.y, self.theta = pose.X(), pose.Y(), pose.rotation().degrees()
        #
        # # attempt to update the real robot's odometry
        # self.distances = [pos + tm_diff * self.spark_dict[drive]['velocity'].value for pos, drive in zip(self.distances, self.spark_drives)]
        # [self.spark_dict[drive]['position'].set(self.spark_dict[drive]['position'].value + tm_diff * self.spark_dict[drive]['velocity'].value ) for drive in self.spark_drives]
        #
        # # TODO - why does this not take care of itself if I just update the simmed SPARK's position?
        # swerve_positions = [SwerveModulePosition(distance=dist, angle=m.angle) for m, dist in zip(module_states, self.distances)]
        # self.robot.container.swerve.pose_estimator.update(pose.rotation(), swerve_positions)
        #
        # wpilib.SmartDashboard.putNumberArray('sim_pose', [self.x, self.y, self.theta])
        # wpilib.SmartDashboard.putNumberArray('drive_pose', [self.x, self.y, self.theta])  # need this for 2429 python dashboard to update
        # now we do this in the periodic

        self.navx_yaw.set(self.navx_yaw.get() - math.degrees(speeds.omega * tm_diff))

        # move the elevator based on controller input
        self.update_elevator_positions()

        #get coral
        if not self.robot.container.elevator.get_has_coral():
            self.has_coral = self.update_intake_coral()
            self.robot.container.elevator.set_has_coral(self.has_coral)
        wpilib.SmartDashboard.putBoolean("Coral Acquired", self.has_coral)

    def update_elevator_positions(self):
        if self.robot is None:
            raise ValueError("Robot is not defined")
        
        self.elevator_height_sim = self.robot.container.elevator.get_height() * (constants.ElevatorConstants.k_elevator_sim_max_height / constants.ElevatorConstants.k_elevator_max_height)
        self.shoulder_pivot = self.robot.container.double_pivot.get_shoulder_pivot()
        self.wrist_color = constants.ElevatorConstants.k_positions[self.robot.container.elevator.get_target_pos()]["wrist_color_for_setColor"]
        
        sm.front_elevator.components["elevator_right"]["ligament"].setLength(self.elevator_height_sim)
        sm.front_elevator.components["elevator_left"]["ligament"].setLength(self.elevator_height_sim)
        
        sm.side_elevator.components["elevator_side"]["ligament"].setLength(self.elevator_height_sim)
        sm.side_elevator.components["double_pivot_shoulder"]["ligament"].setAngle(self.shoulder_pivot)
        sm.side_elevator.components["wrist"]["ligament"].setColor(self.wrist_color)

    def update_intake_coral(self): #if robot is in range of coral + robot is at ground position, then intake. TODO: 'also if robot is at coral station position'
        for coord in [valid_coord for valid_coord in constants.ElevatorConstants.k_coral_intake_coordinates if valid_coord[2] > 0]:
            if self.distance(coord[0],coord[1]) <= constants.ElevatorConstants.k_robot_radius_sim:                
                elevator_in_range = abs(self.robot.container.elevator.get_height() - constants.ElevatorConstants.k_positions["ground"]["elevator_height"]) <= constants.ElevatorConstants.k_tolerance
                shoulder_in_range = abs(self.robot.container.double_pivot.get_shoulder_pivot() - constants.ElevatorConstants.k_positions["ground"]["shoulder_pivot"]) <= constants.ElevatorConstants.k_tolerance

                if elevator_in_range and shoulder_in_range:
                    return True
        return False

    def update_outtake_coral(self):
        for coord in [valid_coord for valid_coord in constants.ElevatorConstants.k_coral_outtake_coordinates if valid_coord[2] == 0]:
            if self.distance(coord[0],coord[1]) <= constants.ElevatorConstants.k_robot_radius_sim:
                robot_target_pos = self.robot.container.elevator.get_target_pos() #returns "l1", "l2", "l3", etc
                
                elevator_in_range = abs(self.robot.container.elevator.get_height() - constants.ElevatorConstants.k_positions[robot_target_pos]["elevator_height"]) <= constants.ElevatorConstants.k_tolerance
                shoulder_in_range = abs(self.robot.container.double_pivot.get_shoulder_pivot() - constants.ElevatorConstants.k_positions[robot_target_pos]["shoulder_pivot"]) <= constants.ElevatorConstants.k_tolerance

                if elevator_in_range and shoulder_in_range:
                    return True
        return False

    def distance(self, x, y):
        current_robot_pose = self.physics_controller.get_pose()
        return math.sqrt((current_robot_pose.X() - x) ** 2 + (current_robot_pose.Y() - y) ** 2)